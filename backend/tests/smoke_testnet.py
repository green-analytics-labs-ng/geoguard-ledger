"""Live smoke test against a deployed GeoGuard Ledger contract on Testnet.

The unit suites prove the contract behaves correctly under simulation and that
the backend wraps it correctly. Neither proves that the contract *actually
deployed on the network* exposes the operations the backend calls. This script
closes that gap: it drives the real client code in ``app.services.soroban``
against a real deployment and reports what happened.

It is deliberately not named ``test_*.py``, so pytest never collects it — it
needs network access, a deployed contract, and (for the write half) a funded
Testnet account, none of which belong in the unit suite.

Usage
-----

Run from ``backend/``:

    # Interface and read checks only. Needs no account and spends no fees.
    uv run python -m tests.smoke_testnet --read-only

    # Full round trip: anchors, proves inclusion, renews TTLs, spends fees.
    SMOKE_TEST_SIGNER_SECRET=S... uv run python -m tests.smoke_testnet

Environment
-----------

``CONTRACT_ID``
    Deployed contract to test. Required (or pass ``--contract-id``).
``SOROBAN_RPC_URL``
    RPC endpoint. Defaults to the configured (Testnet) value.
``SMOKE_TEST_SIGNER_SECRET``
    Funded secret key used for every write. Falls back to ``DEPLOYER_SECRET``
    and then ``TTL_RENEWAL_SIGNER_SECRET``, so an environment already set up for
    a manual deploy or the renewal job needs no extra configuration.

Exit codes
----------

``0`` every check passed, ``1`` at least one check failed, ``2`` misconfigured
(no contract to test, or a write run with no funded signer).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import secrets
import sys
from dataclasses import dataclass
from typing import Any

from stellar_sdk import (
    Account,
    Keypair,
    SorobanServer,
    TransactionBuilder,
    TransactionEnvelope,
    scval,
)
from stellar_sdk.xdr import SCVal as XDR_SCVal

from app.config import settings
from app.services import merkle
from app.services.soroban import (
    build_anchor_root_transaction,
    build_anchor_transaction,
    check_rpc_connectivity,
    renew_record_ttl_on_chain,
    renew_root_ttl_on_chain,
    submit_transaction,
    verify_inclusion_on_chain,
    verify_on_chain,
)

# Score written by the anchor check, and the fixed-point value the contract must
# report back for it (0.42 -> 4200 in the contract's u32 encoding).
ANOMALY_SCORE = 0.42
EXPECTED_FIXED_SCORE = 4200

# Secrets consulted, in order, for the funded account that signs every write.
SIGNER_ENV_VARS = (
    "SMOKE_TEST_SIGNER_SECRET",
    "DEPLOYER_SECRET",
    "TTL_RENEWAL_SIGNER_SECRET",
)

COUNTER_FUNCTIONS = ("get_total_anchored", "get_total_batches")


@dataclass
class Check:
    """One reported assertion, kept so the summary can be printed at the end."""

    name: str
    ok: bool
    detail: str = ""


class Reporter:
    """Prints each check as it runs and tracks whether any of them failed."""

    def __init__(self) -> None:
        self.checks: list[Check] = []

    def record(self, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append(Check(name, ok, detail))
        suffix = f" — {detail}" if detail else ""
        print(f"  {'PASS' if ok else 'FAIL'}  {name}{suffix}")

    @property
    def failed(self) -> list[Check]:
        return [check for check in self.checks if not check.ok]

    def summary(self) -> None:
        print()
        print("=" * 72)
        print(f" {len(self.checks) - len(self.failed)}/{len(self.checks)} checks passed")
        for check in self.failed:
            print(f"   FAIL  {check.name}" + (f" — {check.detail}" if check.detail else ""))
        print("=" * 72)


def _random_hash() -> str:
    """A fresh 32-byte hex hash, so reruns never collide with earlier anchors."""
    return secrets.token_hex(32)


def _explorer_url(tx_hash: str) -> str:
    """Best-effort explorer link, only for a network whose URL we know."""
    if "testnet" in settings.soroban_rpc_url:
        return f"https://stellar.expert/explorer/testnet/tx/{tx_hash}"
    return ""


async def _sign_and_submit(unsigned_xdr: str, signer: Keypair) -> dict[str, Any]:
    """Sign an XDR the backend assembled and submit it, as the frontend would."""
    envelope = TransactionEnvelope.from_xdr(unsigned_xdr, settings.soroban_network_passphrase)
    envelope.sign(signer)
    return await submit_transaction(envelope.to_xdr())


async def _simulate(server: SorobanServer, function_name: str, args: list[Any]) -> tuple[bool, Any]:
    """Simulate a read-only invocation and decode its result.

    The probe is raw SDK rather than a call into ``app.services.soroban`` on
    purpose: the point is to ask the deployed contract what it supports before
    trusting any wrapper. Returns ``(succeeded, result_or_error_detail)``; on
    failure the detail is the full host error, whose first line is the summary
    and whose event log names the missing function.
    """
    probe = Keypair.random()
    envelope = (
        TransactionBuilder(
            Account(probe.public_key, 0),
            settings.soroban_network_passphrase,
            base_fee=100,
        )
        .append_invoke_contract_function_op(
            contract_id=settings.contract_id,
            function_name=function_name,
            parameters=args,
        )
        .set_timeout(300)
        .build()
    )

    simulation = await asyncio.to_thread(server.simulate_transaction, envelope)
    if simulation.error:
        return False, str(simulation.error)
    if not simulation.results:
        return False, "simulation returned no result"

    return True, scval.to_native(XDR_SCVal.from_xdr(simulation.results[0].xdr))


async def check_connectivity(report: Reporter) -> None:
    """Confirm the RPC endpoint answers at all before blaming anything else."""
    reachable = await check_rpc_connectivity()
    report.record("Soroban RPC reachable", reachable, settings.soroban_rpc_url)


async def check_interface(report: Reporter, server: SorobanServer) -> None:
    """Probe the entry points the backend depends on.

    This is the check that catches a stale deployment. A contract deployed
    before batching existed still answers ``get_total_anchored`` while
    answering "trying to invoke non-existent contract function" for
    ``get_total_batches``, ``verify_inclusion`` and ``extend_root_ttl`` — so
    batch anchoring and renewal would fail at runtime while every unit test
    stayed green.
    """
    print("\nContract interface")
    probes: list[tuple[str, list[Any], bool]] = [
        ("get_total_anchored", [], True),
        ("get_total_batches", [], True),
        (
            "verify_inclusion",
            [
                scval.to_bytes(bytes.fromhex(_random_hash())),
                scval.to_bytes(bytes.fromhex(_random_hash())),
                scval.to_uint32(0),
                scval.to_vec([]),
            ],
            False,
        ),
    ]

    for function_name, args, expect_int in probes:
        ok, result = await _simulate(server, function_name, args)
        if not ok:
            detail = str(result)
            # The host error's event log names the function it could not find,
            # which is how a stale deployment is told apart from a broken RPC.
            if "non-existent contract function" in detail:
                detail = f"function not present in the deployed contract — redeploy: {detail}"
            report.record(f"{function_name}() available", False, detail.splitlines()[0])
            continue

        well_typed = isinstance(result, int) if expect_int else isinstance(result, bool)
        report.record(f"{function_name}() available", well_typed, f"returned {result!r}")


async def check_anchor_record(report: Reporter, signer: Keypair) -> str | None:
    """Anchor a standalone dataset hash and read it back from the network."""
    print("\nStandalone anchor")
    dataset_hash = _random_hash()

    try:
        unsigned_xdr = await build_anchor_transaction(
            signer.public_key,
            dataset_hash,
            {"score": ANOMALY_SCORE, "model_version": settings.ai_model_version},
        )
        result = await _sign_and_submit(unsigned_xdr, signer)
    except (RuntimeError, ValueError) as exc:
        report.record("anchor_hash", False, str(exc).splitlines()[0])
        return None

    report.record("anchor_hash", True, f"tx {result['tx_hash'][:16]}…")
    if url := _explorer_url(result["tx_hash"]):
        print(f"        {url}")

    record = await verify_on_chain(dataset_hash)
    if record is None:
        report.record("verify_integrity returns the record", False, "returned None")
        return dataset_hash

    report.record(
        "verify_integrity returns the record",
        record.get("anomaly_score") == EXPECTED_FIXED_SCORE,
        f"anomaly_score={record.get('anomaly_score')} model={record.get('model_version')}",
    )

    unknown = await verify_on_chain(_random_hash())
    report.record("verify_integrity returns None for an unknown hash", unknown is None)

    return dataset_hash


async def check_batch(report: Reporter, signer: Keypair) -> str | None:
    """Anchor a Merkle root and check a proof against it on-chain."""
    print("\nBatch anchor and inclusion proof")

    leaves = [_random_hash() for _ in range(3)]
    root = merkle.compute_root(leaves)
    index = 1
    proof = merkle.generate_proof(leaves, index)

    # Anchor only if the proof we would submit already verifies locally; if the
    # Python tree and the contract disagreed there is nothing worth paying for.
    if not report.record(
        "proof verifies against the local root",
        merkle.verify_proof(leaves[index], index, proof, root),
    ):
        return None

    try:
        unsigned_xdr = await build_anchor_root_transaction(signer.public_key, root, len(leaves))
        result = await _sign_and_submit(unsigned_xdr, signer)
    except (RuntimeError, ValueError) as exc:
        report.record("anchor_root", False, str(exc).splitlines()[0])
        return None

    report.record("anchor_root", True, f"tx {result['tx_hash'][:16]}…")
    if url := _explorer_url(result["tx_hash"]):
        print(f"        {url}")

    verdict = await verify_inclusion_on_chain(root, leaves[index], index, proof)
    report.record(
        "verify_inclusion accepts a valid proof", verdict is True, f"returned {verdict!r}"
    )

    # Same proof, different leaf position: the recomputed root cannot match,
    # which is what stops a batch member from claiming a sibling's slot.
    tampered = await verify_inclusion_on_chain(root, leaves[index], index + 1, proof)
    report.record(
        "verify_inclusion rejects a wrong index",
        tampered is False,
        f"returned {tampered!r}",
    )

    return root


async def check_renewals(
    report: Reporter,
    dataset_hash: str | None,
    merkle_root: str | None,
) -> None:
    """Exercise both renewal entry points the scheduled job depends on.

    Both entries were just written, so these are no-ops on-chain — the contract
    only extends an entry once it drops below its renewal margin. A no-op call
    still submits a transaction and still validates the argument encoding and
    the operational signature, which is the seam worth testing here.
    """
    print("\nTTL renewal")
    extend_to = settings.ttl_renewal_extend_to_ledgers

    if dataset_hash is None:
        report.record("extend_ttl (record)", False, "skipped: no anchored record")
    else:
        try:
            result = await renew_record_ttl_on_chain(dataset_hash, extend_to)
            report.record("extend_ttl (record)", True, f"tx {result['tx_hash'][:16]}…")
        except (RuntimeError, ValueError) as exc:
            report.record("extend_ttl (record)", False, str(exc).splitlines()[0])

    if merkle_root is None:
        report.record("extend_root_ttl (root)", False, "skipped: no anchored root")
    else:
        try:
            result = await renew_root_ttl_on_chain(merkle_root, extend_to)
            report.record("extend_root_ttl (root)", True, f"tx {result['tx_hash'][:16]}…")
        except (RuntimeError, ValueError) as exc:
            report.record("extend_root_ttl (root)", False, str(exc).splitlines()[0])


async def _read_counters(server: SorobanServer) -> tuple[int, int]:
    """Read both global counters, or 0 where the deployed contract lacks one."""
    values: list[int] = []
    for function_name in COUNTER_FUNCTIONS:
        ok, result = await _simulate(server, function_name, [])
        values.append(result if ok and isinstance(result, int) else 0)
    return values[0], values[1]


async def check_counters(report: Reporter, server: SorobanServer, before: tuple[int, int]) -> None:
    """Confirm the counters moved, i.e. the writes actually landed on-chain."""
    print("\nCounters")
    after = await _read_counters(server)

    for function_name, previous, current in zip(COUNTER_FUNCTIONS, before, after, strict=True):
        report.record(
            f"{function_name} advanced",
            current > previous,
            f"{previous} -> {current}",
        )


def _resolve_signer() -> tuple[str, str] | None:
    """Find the funded account used for writes, as ``(env_var, secret)``."""
    for var in SIGNER_ENV_VARS:
        secret = os.environ.get(var, "").strip()
        if secret:
            return var, secret
    return None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke test a deployed GeoGuard Ledger contract on Testnet.",
    )
    parser.add_argument(
        "--contract-id",
        default=None,
        help="Contract to test. Defaults to the CONTRACT_ID setting.",
    )
    parser.add_argument(
        "--rpc-url",
        default=None,
        help="Soroban RPC endpoint. Defaults to the SOROBAN_RPC_URL setting.",
    )
    parser.add_argument(
        "--read-only",
        action="store_true",
        help="Run the interface and read checks only; no signer, no fees.",
    )
    return parser.parse_args(argv)


async def run(args: argparse.Namespace) -> int:
    if args.contract_id:
        settings.contract_id = args.contract_id
    if args.rpc_url:
        settings.soroban_rpc_url = args.rpc_url

    if not settings.contract_id:
        print("error: no contract to test — set CONTRACT_ID or pass --contract-id", file=sys.stderr)
        return 2

    signer: Keypair | None = None
    signer_env_var: str | None = None
    if not args.read_only:
        resolved = _resolve_signer()
        if resolved is None:
            print(
                "error: no funded signer — set SMOKE_TEST_SIGNER_SECRET (or DEPLOYER_SECRET), "
                "or pass --read-only to skip the write checks",
                file=sys.stderr,
            )
            return 2

        signer_env_var, secret = resolved
        signer = Keypair.from_secret(secret)
        # Renewal reads the operational key from settings. Point it at the same
        # account so one funded key covers every check in this script.
        settings.ttl_renewal_signer_secret = secret

    print("=" * 72)
    print(" GeoGuard Ledger — Testnet smoke test")
    print(f" contract: {settings.contract_id}")
    print(f" rpc:      {settings.soroban_rpc_url}")
    print(f" mode:     {'read-only' if args.read_only else 'full'}")
    if signer is not None:
        print(f" signer:   {signer_env_var} ({signer.public_key[:8]}…)")
    print("=" * 72)

    report = Reporter()
    server = SorobanServer(settings.soroban_rpc_url)

    await check_connectivity(report)
    await check_interface(report, server)

    if args.read_only:
        report.summary()
        print("\nRead-only mode: write checks skipped.")
        return 1 if report.failed else 0

    assert signer is not None  # guaranteed by the guard above
    before = await _read_counters(server)
    dataset_hash = await check_anchor_record(report, signer)
    merkle_root = await check_batch(report, signer)
    await check_renewals(report, dataset_hash, merkle_root)
    await check_counters(report, server, before)

    report.summary()
    return 1 if report.failed else 0


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(run(parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
