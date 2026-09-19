"""Unit tests for the two places the backend actually talks to the network.

``_build_and_prepare_unsigned`` (shared by the dataset and batch anchor paths)
turns a contract call into an unsigned envelope, and ``submit_transaction``
relays a researcher-signed one. Both are faked at the ``SorobanServer``
boundary, so the real ``stellar-sdk`` envelope handling runs without a network.
"""

import pytest
from stellar_sdk import Account, Asset, Keypair, StrKey, TransactionBuilder, TransactionEnvelope
from stellar_sdk.exceptions import AccountNotFoundException
from stellar_sdk.soroban_server import GetTransactionStatus

from app.config import settings
from app.core.exceptions import AnchorAlreadyExistsError, SubmitterAccountNotFoundError
from app.services import soroban
from app.services.soroban import FRIENDBOT_URL
from tests.conftest import MOCK_LEDGER, MOCK_TX_HASH

# A syntactically valid contract id, which is all the SDK needs to build the
# invoke operation. Nothing is simulated for real.
CONTRACT_ID = StrKey.encode_contract(bytes(32))
SUBMITTER = Keypair.random().public_key
DATASET_HASH = "ab" * 32
MERKLE_ROOT = "cd" * 32
ANOMALY_REPORT = {"score": 0.42, "model_version": "isoforest_v1", "flags": [], "summary": ""}


# ── Fake SorobanServer ────────────────────────────────────────────
# Only the methods the service calls. The service offloads them through
# ``asyncio.to_thread``, so these are plain synchronous callables.


class _Simulation:
    def __init__(self, error: str | None = None) -> None:
        self.error = error
        self.results: list[object] = []


class _BuildServer:
    """Answers account loading and simulation for the build path."""

    def __init__(
        self,
        error: str | None = None,
        *,
        load_error: Exception | None = None,
        simulate_error: Exception | None = None,
    ) -> None:
        self.error = error
        self.load_error = load_error
        self.simulate_error = simulate_error
        self.prepared = False

    def load_account(self, address: str) -> Account:
        if self.load_error is not None:
            raise self.load_error
        return Account(address, 1)

    def simulate_transaction(self, envelope: object) -> _Simulation:
        if self.simulate_error is not None:
            raise self.simulate_error
        return _Simulation(self.error)

    def prepare_transaction(self, envelope: object, simulation: object) -> object:
        self.prepared = True
        return envelope


class _SendResponse:
    def __init__(self, tx_hash: str, error_result_xdr: str | None = None) -> None:
        self.hash = tx_hash
        self.error_result_xdr = error_result_xdr
        # A freshly submitted transaction is known to the RPC but not yet in a
        # ledger, which is what NOT_FOUND means here.
        self.status = GetTransactionStatus.NOT_FOUND


class _TxStatus:
    def __init__(self, status: object, ledger: int | None = None) -> None:
        self.status = status
        self.ledger = ledger


class _SubmitServer:
    """Answers submission and polling for the submit path."""

    def __init__(
        self,
        *,
        tx_status: object = None,
        ledger: int | None = None,
        poll_error: Exception | None = None,
        send_error_result_xdr: str | None = None,
    ) -> None:
        self.tx_status = tx_status
        self.ledger = ledger
        self.poll_error = poll_error
        self.send_error_result_xdr = send_error_result_xdr
        self.submitted: object | None = None

    def send_transaction(self, envelope: object) -> _SendResponse:
        self.submitted = envelope
        return _SendResponse(MOCK_TX_HASH, self.send_error_result_xdr)

    def poll_transaction(self, tx_hash: str, timeout: int) -> _TxStatus:
        if self.poll_error is not None:
            raise self.poll_error
        return _TxStatus(self.tx_status, self.ledger)


def _signed_envelope_xdr() -> str:
    """A real, signed envelope the submit path can parse without a network."""
    keypair = Keypair.random()
    envelope = (
        TransactionBuilder(
            Account(keypair.public_key, 1), settings.soroban_network_passphrase, base_fee=100
        )
        .append_payment_op(keypair.public_key, Asset.native(), "1")
        .set_timeout(300)
        .build()
    )
    envelope.sign(keypair)
    return envelope.to_xdr()


# ── Building the unsigned anchor transaction ──────────────────────


@pytest.mark.asyncio
async def test_duplicate_hash_simulation_error_is_a_typed_conflict(monkeypatch):
    """A contract refusal for a known hash becomes AnchorAlreadyExistsError.

    The contract answers ``Error(Contract, #3)`` and anchoring never overwrites,
    so this is a permanent conflict the caller can act on rather than a
    transient simulation failure to retry.
    """
    monkeypatch.setattr(settings, "contract_id", CONTRACT_ID)
    monkeypatch.setattr(soroban, "_get_server", lambda: _BuildServer(error="Error(Contract, #3)"))

    with pytest.raises(AnchorAlreadyExistsError) as caught:
        await soroban.build_anchor_transaction(SUBMITTER, DATASET_HASH, ANOMALY_REPORT)

    assert caught.value.status_code == 409
    assert "hash" in caught.value.message


@pytest.mark.asyncio
async def test_duplicate_root_simulation_error_is_a_typed_conflict(monkeypatch):
    """Code 6 is the batch-root variant, which has to carry its own message."""
    monkeypatch.setattr(settings, "contract_id", CONTRACT_ID)
    monkeypatch.setattr(soroban, "_get_server", lambda: _BuildServer(error="Error(Contract, #6)"))

    with pytest.raises(AnchorAlreadyExistsError, match="Merkle root"):
        await soroban.build_anchor_root_transaction(SUBMITTER, MERKLE_ROOT, 2)


@pytest.mark.asyncio
async def test_any_other_simulation_error_surfaces_its_reason(monkeypatch):
    """A failure that is not a duplicate must not be mislabelled as one."""
    monkeypatch.setattr(settings, "contract_id", CONTRACT_ID)
    monkeypatch.setattr(soroban, "_get_server", lambda: _BuildServer(error="Error(Contract, #7)"))

    with pytest.raises(RuntimeError, match=r"Error\(Contract, #7\)"):
        await soroban.build_anchor_root_transaction(SUBMITTER, MERKLE_ROOT, 2)


@pytest.mark.asyncio
async def test_build_returns_the_prepared_unsigned_envelope(monkeypatch):
    """On success the simulation result is baked in and the XDR handed back."""
    server = _BuildServer()
    monkeypatch.setattr(settings, "contract_id", CONTRACT_ID)
    monkeypatch.setattr(soroban, "_get_server", lambda: server)

    xdr = await soroban.build_anchor_root_transaction(SUBMITTER, MERKLE_ROOT, 3)

    assert server.prepared
    assert isinstance(xdr, str)
    # The frontend has to be able to parse exactly what we hand it.
    assert TransactionEnvelope.from_xdr(xdr, settings.soroban_network_passphrase)


@pytest.mark.asyncio
async def test_build_refuses_without_a_contract_id(monkeypatch):
    """No contract means nothing to invoke, so the build must fail loudly."""
    monkeypatch.setattr(settings, "contract_id", "")

    with pytest.raises(ValueError, match="CONTRACT_ID"):
        await soroban.build_anchor_root_transaction(SUBMITTER, MERKLE_ROOT, 1)


@pytest.mark.asyncio
async def test_unfunded_submitter_points_at_the_faucet(monkeypatch):
    """A wallet with no on-chain account must be told how to fund it, not get a 500.

    The SDK raises ``AccountNotFoundException`` while loading the sequence
    account; that has to reach the user as a fixable condition.
    """
    monkeypatch.setattr(settings, "contract_id", CONTRACT_ID)
    monkeypatch.setattr(settings, "soroban_network_passphrase", soroban.TESTNET_NETWORK_PASSPHRASE)
    server = _BuildServer(load_error=AccountNotFoundException(SUBMITTER))
    monkeypatch.setattr(soroban, "_get_server", lambda: server)

    with pytest.raises(SubmitterAccountNotFoundError) as caught:
        await soroban.build_anchor_transaction(SUBMITTER, DATASET_HASH, ANOMALY_REPORT)

    assert SUBMITTER in caught.value.message
    assert FRIENDBOT_URL in caught.value.message


@pytest.mark.asyncio
async def test_simulation_transport_failure_becomes_a_runtime_error(monkeypatch):
    """A dropped RPC connection while simulating is a failed build, not a revert."""
    monkeypatch.setattr(settings, "contract_id", CONTRACT_ID)
    server = _BuildServer(simulate_error=RuntimeError("RPC connection reset"))
    monkeypatch.setattr(soroban, "_get_server", lambda: server)

    with pytest.raises(RuntimeError, match="Transaction simulation failed"):
        await soroban.build_anchor_root_transaction(SUBMITTER, MERKLE_ROOT, 2)


# ── Submitting a signed transaction ───────────────────────────────


@pytest.mark.asyncio
async def test_submit_returns_pending_then_resolves_to_success(monkeypatch):
    """The RPC acks with a hash, then polling settles on a ledger and hash."""
    server = _SubmitServer(tx_status=GetTransactionStatus.SUCCESS, ledger=MOCK_LEDGER)
    monkeypatch.setattr(soroban, "_get_server", lambda: server)

    result = await soroban.submit_transaction(_signed_envelope_xdr())

    assert result == {"tx_hash": MOCK_TX_HASH, "ledger": MOCK_LEDGER}
    assert server.submitted is not None


@pytest.mark.asyncio
async def test_submit_surfaces_a_failed_status(monkeypatch):
    """A FAILED transaction reports why instead of looking like a success."""
    server = _SubmitServer(tx_status=GetTransactionStatus.FAILED)
    monkeypatch.setattr(soroban, "_get_server", lambda: server)

    with pytest.raises(RuntimeError) as caught:
        await soroban.submit_transaction(_signed_envelope_xdr())

    assert "failed on-chain" in str(caught.value)
    assert "FAILED" in str(caught.value)


@pytest.mark.asyncio
async def test_polling_failure_becomes_a_retryable_timeout(monkeypatch):
    """Losing the poll is transient, so it must not read as an on-chain failure."""
    server = _SubmitServer(poll_error=RuntimeError("RPC connection reset"))
    monkeypatch.setattr(soroban, "_get_server", lambda: server)

    with pytest.raises(TimeoutError, match="confirmation timed out"):
        await soroban.submit_transaction(_signed_envelope_xdr())


@pytest.mark.asyncio
async def test_rejected_submission_reports_the_rpc_error(monkeypatch):
    """An RPC that rejects the envelope outright must surface its error result."""
    server = _SubmitServer(send_error_result_xdr="AAAArejected")
    monkeypatch.setattr(soroban, "_get_server", lambda: server)

    with pytest.raises(RuntimeError, match="submission rejected"):
        await soroban.submit_transaction(_signed_envelope_xdr())


@pytest.mark.asyncio
async def test_malformed_client_xdr_is_rejected_before_any_submission(monkeypatch):
    """Garbage from the client fails locally instead of being relayed to the RPC."""
    server = _SubmitServer(tx_status=GetTransactionStatus.SUCCESS, ledger=1)
    monkeypatch.setattr(soroban, "_get_server", lambda: server)

    with pytest.raises(ValueError):
        await soroban.submit_transaction("not-a-valid-xdr")

    assert server.submitted is None
