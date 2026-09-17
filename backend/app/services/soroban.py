"""Soroban RPC client for transaction building, submission, and verification.

Uses stellar-sdk v15 with SorobanServer for RPC communication.
All synchronous SDK calls are offloaded to a thread pool to avoid
blocking the FastAPI async event loop.
"""

import asyncio
import logging
from typing import Any

from stellar_sdk import (
    Account,
    Keypair,
    SorobanServer,
    TransactionBuilder,
    TransactionEnvelope,
    scval,
)
from stellar_sdk import (
    Address as StellarAddress,
)
from stellar_sdk.exceptions import AccountNotFoundException, NotFoundError
from stellar_sdk.soroban_server import GetTransactionStatus
from stellar_sdk.xdr import SCValType

from app.config import settings
from app.core.exceptions import SubmitterAccountNotFoundError

logger = logging.getLogger(__name__)

# ── Network funding ───────────────────────────────────────────────
# The network passphrase is the only thing here that separates Testnet from
# Mainnet, and Friendbot's faucet exists on Testnet only — Mainnet accounts have
# to be funded with real XLM, so the hint has to differ per network.
TESTNET_NETWORK_PASSPHRASE = "Test SDF Network ; September 2015"
FRIENDBOT_URL = "https://friendbot.stellar.org"


def _unfunded_submitter_error(submitter_address: str) -> SubmitterAccountNotFoundError:
    """Build a user-actionable error for a submitter with no on-chain account.

    An anchor transaction uses the submitter as its source, so the account has
    to exist on-chain to supply a sequence number. A newly generated wallet is
    not an account until something funds it — the normal state for a first-time
    user, and one the SDK reports without any hint of how to resolve it.
    """
    if settings.soroban_network_passphrase == TESTNET_NETWORK_PASSPHRASE:
        return SubmitterAccountNotFoundError(
            f"Your Stellar account {submitter_address} is not funded on Testnet, so "
            f"it has no sequence number to sign the anchor with. Fund it at "
            f"{FRIENDBOT_URL}?addr={submitter_address} (free testnet XLM), then "
            f"reconnect your wallet and try again."
        )
    return SubmitterAccountNotFoundError(
        f"Your Stellar account {submitter_address} does not exist on Mainnet. It "
        f"must be funded with at least the base reserve before it can sign the "
        f"anchor transaction."
    )


# ── Anomaly score fixed-point conversion ──────────────────────────
# The contract stores anomaly_score as u32 in 0–10000 range
# (representing 0.00% – 100.00%).
ANOMALY_SCORE_MULTIPLIER = 10_000


def _score_to_fixed(score: float) -> int:
    """Convert a 0.0–1.0 anomaly score to the contract's fixed-point u32."""
    clamped = max(0.0, min(1.0, score))
    return int(clamped * ANOMALY_SCORE_MULTIPLIER)


def _hex_to_bytes(hex_str: str) -> bytes:
    """Convert a hex-encoded SHA-256 hash string to raw bytes."""
    return bytes.fromhex(hex_str)


_server: SorobanServer | None = None


def _get_server() -> SorobanServer:
    """Return a lazily-initialized singleton SorobanServer instance.

    Creating a new server per call would create a fresh HTTP session
    each time — reusing a single instance reduces connection churn.
    """
    global _server
    if _server is None:
        _server = SorobanServer(settings.soroban_rpc_url)
    return _server


# ── Connectivity ──────────────────────────────────────────────────


async def check_rpc_connectivity() -> bool:
    """Probe the configured Soroban RPC endpoint for real.

    Calls the RPC's ``getHealth`` method with a short timeout so the health
    endpoint reflects reality instead of assuming connectivity. Any failure
    (timeout, HTTP error, error response, or a non-healthy status) reports the
    node as unreachable.

    Returns:
        ``True`` only when the RPC answered and reported a healthy status.
    """
    server = _get_server()

    try:
        health = await asyncio.wait_for(
            asyncio.to_thread(server.get_health),
            timeout=settings.soroban_rpc_health_timeout_seconds,
        )
    except Exception as exc:  # noqa: BLE001 - any failure means "unreachable"
        logger.warning("Soroban RPC health check failed: %s", exc)
        return False

    if health.status != "healthy":
        logger.warning("Soroban RPC reported unhealthy status: %s", health.status)
        return False

    return True


# ── Transaction Building ──────────────────────────────────────────


async def build_anchor_transaction(
    submitter_address: str,
    dataset_hash: str,
    anomaly_report: dict[str, Any],
) -> str:
    """Build an unsigned Soroban transaction for anchoring a dataset hash.

    Uses the simulation-first flow:
    1. Load the submitter's on-chain account for sequence number.
    2. Build a base transaction with the invoke operation.
    3. Simulate to get the resource footprint and cost.
    4. Assemble the final unsigned transaction using prepare_transaction.
    5. Return the transaction XDR as a base64-encoded string.

    Args:
        submitter_address: Stellar public key (G…) of the researcher.
        dataset_hash: SHA-256 hex string (64 chars).
        anomaly_report: Dict with keys ``score`` (float 0–1),
            ``model_version`` (str), ``flags``, ``summary``.

    Returns:
        Unsigned transaction envelope XDR (base64 string).
    """
    # Build invoke arguments as SCVal objects for the contract function.
    # NOTE: scval.to_*() creates SCVal from Python value (Python->SCVal serialization).
    # scval.from_*() does the reverse (SCVal->Python deserialization).
    invoke_args = [
        StellarAddress(submitter_address).to_xdr_sc_val(),  # Address
        scval.to_bytes(_hex_to_bytes(dataset_hash)),  # BytesN<32>
        scval.to_uint32(_score_to_fixed(anomaly_report["score"])),  # u32
        scval.to_symbol(anomaly_report["model_version"]),  # Symbol
    ]

    return await _build_and_prepare_unsigned(
        submitter_address,
        "anchor_hash",
        invoke_args,
        log_context=f"hash={dataset_hash[:12]}",
    )


async def _build_and_prepare_unsigned(
    submitter_address: str,
    function_name: str,
    invoke_args: list[Any],
    log_context: str = "",
) -> str:
    """Build a contract invocation, simulate it, and return the assembled XDR.

    Shared by every anchoring flow:
    1. Load the submitter's on-chain account for the sequence number.
    2. Build a base transaction with the invoke operation.
    3. Simulate to obtain the resource footprint and cost.
    4. Assemble the final unsigned transaction with ``prepare_transaction`` so
       the frontend only has to sign it.

    Raises:
        ValueError: If ``CONTRACT_ID`` is unset.
        SubmitterAccountNotFoundError: If the submitter has no on-chain account.
        RuntimeError: If simulation fails or the contract rejects the call.
    """
    if not settings.contract_id:
        raise ValueError("CONTRACT_ID not configured — cannot build transaction")

    server = _get_server()

    # 1. Load the submitter's account (needed for sequence number).
    #    Offloaded to thread pool to avoid blocking the event loop.
    try:
        source_account: Account = await asyncio.to_thread(server.load_account, submitter_address)
    except (AccountNotFoundException, NotFoundError):
        # `AccountNotFoundException` is what the SDK actually raises and it
        # derives from `SdkError`, not from `NotFoundError`, so catching only
        # the latter let it escape as an unhandled 500. Both are named because
        # `NotFoundError` is still the documented base for other RPC lookups.
        raise _unfunded_submitter_error(submitter_address) from None

    # 2. Build the transaction envelope (v15: build() returns TransactionEnvelope directly)
    envelope = (
        TransactionBuilder(
            source_account,
            settings.soroban_network_passphrase,
            base_fee=100,
        )
        .append_invoke_contract_function_op(
            contract_id=settings.contract_id,
            function_name=function_name,
            parameters=invoke_args,
        )
        .set_timeout(300)
        .build()
    )

    logger.debug(
        "Simulating %s (%s) for submitter=%s",
        function_name,
        log_context,
        submitter_address[:8],
    )
    try:
        simulation = await asyncio.to_thread(server.simulate_transaction, envelope)
    except Exception as exc:
        logger.error("Simulation failed for %s %s: %s", function_name, log_context, exc)
        raise RuntimeError(f"Transaction simulation failed: {exc}") from exc

    if simulation.error:
        raise RuntimeError(f"Transaction simulation error: {simulation.error}")

    # 3. Assemble the transaction with simulation results.
    #    prepare_transaction bakes in the resource footprint, fee, and
    #    authorization entries so the frontend only needs to sign it.
    assembled_tx: TransactionEnvelope = await asyncio.to_thread(
        server.prepare_transaction, envelope, simulation
    )

    return str(assembled_tx.to_xdr())


async def build_anchor_root_transaction(
    submitter_address: str,
    merkle_root: str,
    leaf_count: int,
) -> str:
    """Build an unsigned Soroban transaction anchoring a Merkle root.

    Anchors one root for a whole batch of datasets instead of one entry per
    dataset, which keeps the on-chain storage cost flat as submissions grow.

    Args:
        submitter_address: Stellar public key (G…) of the researcher.
        merkle_root: SHA-256 hex string (64 chars) of the batch root.
        leaf_count: Number of dataset leaves committed to by the root.

    Returns:
        Unsigned transaction envelope XDR (base64 string).
    """
    invoke_args = [
        StellarAddress(submitter_address).to_xdr_sc_val(),  # Address
        scval.to_bytes(_hex_to_bytes(merkle_root)),  # BytesN<32>
        scval.to_uint32(leaf_count),  # u32
    ]

    return await _build_and_prepare_unsigned(
        submitter_address,
        "anchor_root",
        invoke_args,
        log_context=f"root={merkle_root[:12]} leaves={leaf_count}",
    )


# ── Root TTL Renewal (operational signer) ────────────────────────


def _renewal_signer() -> Keypair:
    """Load the operational account that pays root TTL renewal fees.

    Renewal is a state-changing call, so unlike anchoring it cannot be handed
    to the researcher to sign — the backend signs it itself. This is therefore
    the one place the service holds a secret key, and it is never logged.

    Raises:
        ValueError: If no renewal signer is configured.
    """
    if not settings.ttl_renewal_signer_secret:
        raise ValueError("TTL_RENEWAL_SIGNER_SECRET not configured — cannot renew root TTL")
    return Keypair.from_secret(settings.ttl_renewal_signer_secret)


async def _renew_ttl_on_chain(
    function_name: str,
    entry_key: str,
    extend_to_ledgers: int,
) -> dict[str, Any]:
    """Extend a persistent entry's TTL, signed by the operational account.

    Both renewal entry points (`extend_root_ttl` for a batch root, `extend_ttl`
    for an individual record) share this shape: one BytesN<32> key and a target
    ledger count, no argument identifying who is asking.

    Renewal is a state-changing call, so unlike anchoring it cannot be handed to
    the researcher to sign — the backend signs it with the operational account.
    Both functions are permissionless and can only push an expiry out, so that
    account can never alter or forge a record: it only pays rent. A call against
    an entry that is still well covered is a no-op on-chain.

    Args:
        function_name: Contract function to invoke.
        entry_key: Hex key of the entry (Merkle root, or dataset hash).
        extend_to_ledgers: Ledger count to extend that entry to.

    Returns:
        Dict with ``tx_hash`` (str) and ``ledger`` (int).

    Raises:
        ValueError: If the contract ID or the renewal signer is not configured.
        RuntimeError: If simulation or submission fails.
    """
    signer = _renewal_signer()

    invoke_args = [
        scval.to_bytes(_hex_to_bytes(entry_key)),  # BytesN<32>
        scval.to_uint32(extend_to_ledgers),  # u32
    ]

    # Build and simulate with the payer as source: it pays the fee, so it has to
    # exist and be funded on-chain.
    unsigned_xdr = await _build_and_prepare_unsigned(
        signer.public_key,
        function_name,
        invoke_args,
        log_context=f"{function_name} key={entry_key[:12]} extend_to={extend_to_ledgers}",
    )

    # Sign only after prepare_transaction, which bakes in the resource footprint
    # and fee and so changes the transaction hash that gets signed.
    envelope = TransactionEnvelope.from_xdr(unsigned_xdr, settings.soroban_network_passphrase)
    envelope.sign(signer)

    return await submit_transaction(envelope.to_xdr())


async def renew_root_ttl_on_chain(
    merkle_root: str,
    extend_to_ledgers: int,
) -> dict[str, Any]:
    """Extend an anchored Merkle root's TTL, covering every dataset in its batch.

    Args:
        merkle_root: Hex Merkle root whose persistent entry should be renewed.
        extend_to_ledgers: Ledger count to extend that entry to.

    Returns:
        Dict with ``tx_hash`` (str) and ``ledger`` (int).
    """
    return await _renew_ttl_on_chain("extend_root_ttl", merkle_root, extend_to_ledgers)


async def renew_record_ttl_on_chain(
    dataset_hash: str,
    extend_to_ledgers: int,
) -> dict[str, Any]:
    """Extend a dataset's own anchor record, for datasets anchored individually.

    A batched dataset has no `Record(hash)` entry of its own, so this is only
    used for the standalone anchoring path.

    Args:
        dataset_hash: Hex SHA-256 hash whose record should be renewed.
        extend_to_ledgers: Ledger count to extend that entry to.

    Returns:
        Dict with ``tx_hash`` (str) and ``ledger`` (int).
    """
    return await _renew_ttl_on_chain("extend_ttl", dataset_hash, extend_to_ledgers)


# ── Transaction Submission ────────────────────────────────────────


async def submit_transaction(signed_xdr: str) -> dict[str, Any]:
    """Submit a researcher-signed transaction to the Stellar network.

    Args:
        signed_xdr: Signed transaction envelope XDR (base64).

    Returns:
        Dict with ``tx_hash`` (str) and ``ledger`` (int).

    Raises:
        RuntimeError: If the transaction fails on-chain.
        TimeoutError: If confirmation takes longer than 60 seconds.
    """
    server = _get_server()
    network_passphrase = settings.soroban_network_passphrase

    # Parse the signed envelope
    envelope = TransactionEnvelope.from_xdr(signed_xdr, network_passphrase)

    # Submit (offloaded to thread pool)
    # v15: send_transaction expects the full TransactionEnvelope, not .transaction
    logger.info("Submitting transaction to Soroban RPC…")
    send_response = await asyncio.to_thread(
        server.send_transaction,
        envelope,
    )

    if send_response.error_result_xdr:
        raise RuntimeError(f"Transaction submission rejected: {send_response.error_result_xdr}")

    tx_hash: str = send_response.hash
    logger.info("Transaction submitted: %s", tx_hash)

    # Poll for confirmation (offloaded to thread pool; up to 60 seconds)
    try:
        tx_status = await asyncio.to_thread(server.poll_transaction, tx_hash, 30)
    except Exception as exc:
        logger.error("Polling failed for tx=%s: %s", tx_hash, exc)
        raise TimeoutError(f"Transaction {tx_hash} confirmation timed out") from exc

    if tx_status.status == GetTransactionStatus.SUCCESS:
        ledger: int = tx_status.ledger if tx_status.ledger is not None else 0
        logger.info("Transaction %s confirmed at ledger %s", tx_hash, ledger)
        return {"tx_hash": tx_hash, "ledger": ledger}

    raise RuntimeError(f"Transaction {tx_hash} failed on-chain. Status: {tx_status.status}")


# ── On-Chain Verification ─────────────────────────────────────────


async def verify_on_chain(dataset_hash: str) -> dict[str, Any] | None:
    """Query the Soroban contract for an anchored dataset record.

    Uses a simulated read-only invocation of ``verify_integrity``.
    Does not submit a real transaction — no gas is consumed.

    Args:
        dataset_hash: SHA-256 hex string (64 chars).

    Returns:
        Dict with the ``AnchorRecord`` fields if found, or ``None``
        if the hash is not on-chain (or the contract is not deployed).
    """
    if not settings.contract_id:
        logger.warning("verify_on_chain called but CONTRACT_ID is not set")
        return None

    server = _get_server()
    network_passphrase = settings.soroban_network_passphrase
    hash_bytes = _hex_to_bytes(dataset_hash)

    invoke_args = [scval.to_bytes(hash_bytes)]  # BytesN<32> SCVal

    # Use a throwaway keypair for simulation — read-only calls don't
    # require a real funded account. The sequence number is ignored
    # during simulation.
    dummy_kp = Keypair.random()
    dummy_account = Account(dummy_kp.public_key, 0)

    # v15: build() returns TransactionEnvelope directly
    envelope = (
        TransactionBuilder(dummy_account, network_passphrase, base_fee=100)
        .append_invoke_contract_function_op(
            contract_id=settings.contract_id,
            function_name="verify_integrity",
            parameters=invoke_args,
        )
        .set_timeout(300)
        .build()
    )

    try:
        simulation = await asyncio.to_thread(server.simulate_transaction, envelope)
    except Exception as exc:
        logger.warning("verify_on_chain simulation failed: %s", exc)
        return None

    if simulation.error or not simulation.results:
        return None

    # The contract returns Option<AnchorRecord>.
    # v15: result has 'xdr' field (SCVal XDR bytes) instead of 'retval'.
    # Parse the XDR bytes back into an SCVal to check the return value.
    result_xdr = simulation.results[0].xdr
    try:
        from stellar_sdk.xdr import SCVal as XDR_SCVal

        # from_xdr accepts both raw bytes AND base64-encoded strings
        retval = XDR_SCVal.from_xdr(result_xdr)
    except Exception as exc:
        logger.warning("Failed to parse verify_integrity result XDR: %s", exc)
        return None

    # Soroban serializes None (Rust Option::None) as SCV_VOID.
    if retval.type == SCValType.SCV_VOID:
        return None

    # Convert the SCVal to a Python dict
    try:
        record = scval.to_native(retval)
    except Exception as exc:
        logger.warning("Failed to parse verify_integrity result: %s", exc)
        return None

    # BytesN<32> fields come back as raw bytes; convert to hex strings for JSON safety
    if isinstance(record.get("dataset_hash"), bytes):  # type: ignore[union-attr]
        record["dataset_hash"] = record["dataset_hash"].hex()  # type: ignore[call-overload,index,union-attr]
    # The submitter field from the contract is an Address object; convert to string.
    # to_string() gives the clean G... address, str() falls back to __repr__.
    submitter = record.get("submitter")  # type: ignore[union-attr]
    if hasattr(submitter, "to_string"):
        record["submitter"] = submitter.to_string()  # type: ignore[call-overload,index,union-attr]
    elif isinstance(submitter, bytes):
        record["submitter"] = submitter.hex()  # type: ignore[call-overload,index]
    elif not isinstance(submitter, str):
        record["submitter"] = str(submitter)  # type: ignore[call-overload,index]

    return record  # type: ignore[return-value]


async def verify_inclusion_on_chain(
    merkle_root: str,
    dataset_hash: str,
    index: int,
    siblings: list[str],
) -> bool | None:
    """Check a Merkle inclusion proof against the anchored root on-chain.

    Simulates a read-only ``verify_inclusion`` call, so no gas is consumed.
    The contract recomputes the root from the leaf and proof, which means a
    third party does not have to trust the backend's own proof check.

    Args:
        merkle_root: Hex Merkle root of the batch.
        dataset_hash: Hex dataset hash whose inclusion is being proven.
        index: Position of the dataset hash within the batch leaves.
        siblings: Bottom-up hex sibling hashes.

    Returns:
        The contract's verdict, or ``None`` when the check could not be
        evaluated (contract not deployed, RPC failure, or unparseable result)
        so callers can distinguish "not included" from "could not check".
    """
    if not settings.contract_id:
        logger.warning("verify_inclusion_on_chain called but CONTRACT_ID is not set")
        return None

    server = _get_server()

    invoke_args = [
        scval.to_bytes(_hex_to_bytes(merkle_root)),  # BytesN<32>
        scval.to_bytes(_hex_to_bytes(dataset_hash)),  # BytesN<32>
        scval.to_uint32(index),  # u32
        scval.to_vec([scval.to_bytes(_hex_to_bytes(s)) for s in siblings]),  # Vec<BytesN<32>>
    ]

    # Read-only simulation needs no funded account.
    dummy_kp = Keypair.random()
    dummy_account = Account(dummy_kp.public_key, 0)

    envelope = (
        TransactionBuilder(dummy_account, settings.soroban_network_passphrase, base_fee=100)
        .append_invoke_contract_function_op(
            contract_id=settings.contract_id,
            function_name="verify_inclusion",
            parameters=invoke_args,
        )
        .set_timeout(300)
        .build()
    )

    try:
        simulation = await asyncio.to_thread(server.simulate_transaction, envelope)
    except Exception as exc:
        logger.warning("verify_inclusion simulation failed: %s", exc)
        return None

    if simulation.error or not simulation.results:
        return None

    try:
        from stellar_sdk.xdr import SCVal as XDR_SCVal

        retval = XDR_SCVal.from_xdr(simulation.results[0].xdr)
        native = scval.to_native(retval)
    except Exception as exc:
        logger.warning("Failed to parse verify_inclusion result: %s", exc)
        return None

    return native if isinstance(native, bool) else None
