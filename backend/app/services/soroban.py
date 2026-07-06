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
    Address as StellarAddress,
    Keypair,
    SorobanServer,
    TransactionBuilder,
    TransactionEnvelope,
    scval,
)
from stellar_sdk.exceptions import NotFoundError
from stellar_sdk.soroban_server import GetTransactionStatus
from stellar_sdk.xdr import SCValType

from app.config import settings

logger = logging.getLogger(__name__)

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
    if not settings.contract_id:
        raise ValueError("CONTRACT_ID not configured — cannot build transaction")

    server = _get_server()
    contract_id = settings.contract_id
    network_passphrase = settings.soroban_network_passphrase

    # 1. Load the submitter's account (needed for sequence number).
    #    Offloaded to thread pool to avoid blocking the event loop.
    try:
        source_account: Account = await asyncio.to_thread(
            server.load_account, submitter_address
        )
    except NotFoundError:
        raise ValueError(
            f"Account {submitter_address} not found on-chain. "
            "Ensure the account exists and is funded on the Stellar network."
        ) from None

    # 2. Build invoke arguments
    hash_bytes = _hex_to_bytes(dataset_hash)
    anomaly_score_u32 = _score_to_fixed(anomaly_report["score"])
    model_version = anomaly_report["model_version"]

    # Build invoke arguments as SCVal objects for the contract function.
    # NOTE: scval.to_*() creates SCVal from Python value (Python->SCVal serialization).
    # scval.from_*() does the reverse (SCVal->Python deserialization).
    invoke_args = [
        StellarAddress(submitter_address).to_xdr_sc_val(),  # Address
        scval.to_bytes(hash_bytes),                          # BytesN<32>
        scval.to_uint32(anomaly_score_u32),                  # u32
        scval.to_symbol(model_version),                      # Symbol
    ]

    # 3. Build the transaction envelope (v15: build() returns TransactionEnvelope directly)
    envelope = (
        TransactionBuilder(source_account, network_passphrase, base_fee=100)
        .append_invoke_contract_function_op(
            contract_id=contract_id,
            function_name="anchor_hash",
            parameters=invoke_args,  # type: ignore[arg-type]
        )
        .set_timeout(300)
        .build()
    )

    logger.debug(
        "Simulating anchor_hash for hash=%s, submitter=%s",
        dataset_hash[:12],
        submitter_address[:8],
    )
    try:
        simulation = await asyncio.to_thread(
            server.simulate_transaction, envelope
        )
    except Exception as exc:
        logger.error("Simulation failed for hash=%s: %s", dataset_hash[:12], exc)
        raise RuntimeError(f"Transaction simulation failed: {exc}") from exc

    if simulation.error:
        raise RuntimeError(f"Transaction simulation error: {simulation.error}")

    # 4. Assemble the transaction with simulation results.
    #    prepare_transaction bakes in the resource footprint, fee, and
    #    authorization entries so the frontend only needs to sign it.
    assembled_tx: TransactionEnvelope = await asyncio.to_thread(
        server.prepare_transaction, envelope, simulation
    )

    return str(assembled_tx.to_xdr())


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
    logger.info("Submitting transaction to Soroban RPC…")
    send_response = await asyncio.to_thread(
        server.send_transaction, envelope.transaction  # type: ignore[arg-type]
    )

    if send_response.error_result_xdr:
        raise RuntimeError(
            f"Transaction submission rejected: {send_response.error_result_xdr}"
        )

    tx_hash: str = send_response.hash
    logger.info("Transaction submitted: %s", tx_hash)

    # Poll for confirmation (offloaded to thread pool; up to 60 seconds)
    try:
        tx_status = await asyncio.to_thread(
            server.poll_transaction, tx_hash, 30
        )
    except Exception as exc:
        logger.error("Polling failed for tx=%s: %s", tx_hash, exc)
        raise TimeoutError(
            f"Transaction {tx_hash} confirmation timed out"
        ) from exc

    if tx_status.status == GetTransactionStatus.SUCCESS:
        ledger: int = tx_status.ledger if tx_status.ledger is not None else 0
        logger.info("Transaction %s confirmed at ledger %s", tx_hash, ledger)
        return {"tx_hash": tx_hash, "ledger": ledger}

    raise RuntimeError(
        f"Transaction {tx_hash} failed on-chain. "
        f"Status: {tx_status.status}"
    )


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
            parameters=invoke_args,  # type: ignore[arg-type]
        )
        .set_timeout(300)
        .build()
    )

    try:
        simulation = await asyncio.to_thread(
            server.simulate_transaction, envelope
        )
    except Exception as exc:
        logger.warning("verify_on_chain simulation failed: %s", exc)
        return None

    if simulation.error or not simulation.results:
        return None

    # The contract returns Option<AnchorRecord>.
    # Soroban serializes None (Rust Option::None) as SCV_VOID.
    retval = simulation.results[0].retval  # type: ignore[attr-defined]
    if retval.type == SCValType.SCV_VOID:
        return None

    # Convert the SCVal to a Python dict
    try:
        record: dict[str, Any] = scval.to_native(retval)  # type: ignore[assignment]
    except Exception as exc:
        logger.warning("Failed to parse verify_integrity result: %s", exc)
        return None

    return record
