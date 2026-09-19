"""Unit tests for the two read-only paths that query the deployed contract.

``verify_on_chain`` answers "is this dataset anchored?" and
``verify_inclusion_on_chain`` answers "does this proof belong to that root?".
Both talk to the RPC by simulating an invocation, so they are faked at the
``SorobanServer`` boundary: the real SCVal encoding and decoding run, without a
network. What matters here is that a failure is reported as "could not check"
(``None``) rather than as a confident "no", and that a found record comes back
JSON-safe.
"""

import pytest
from stellar_sdk import Keypair, StrKey, scval

from app.config import settings
from app.services import soroban

# A syntactically valid contract id, which is all the SDK needs to build the
# invoke operation. Nothing is simulated for real.
CONTRACT_ID = StrKey.encode_contract(bytes(32))
DATASET_HASH = "ab" * 32
MERKLE_ROOT = "cd" * 32


class _Result:
    """One entry of ``simulation.results``: it carries the SCVal XDR."""

    def __init__(self, xdr: str) -> None:
        self.xdr = xdr


class _Simulation:
    def __init__(self, error: str | None = None, results: list[_Result] | None = None) -> None:
        self.error = error
        self.results = results or []


class _VerifyServer:
    """Answers simulation for the read-only paths, or fails on demand."""

    def __init__(self, simulation: _Simulation | None = None, *, raises: Exception | None = None):
        self._simulation = simulation
        self._raises = raises
        self.call_count = 0

    def simulate_transaction(self, envelope: object) -> _Simulation:
        self.call_count += 1
        if self._raises is not None:
            raise self._raises
        assert self._simulation is not None
        return self._simulation


def _result(value) -> _Simulation:
    """A successful simulation whose first result is ``value`` as an SCVal."""
    return _Simulation(results=[_Result(value.to_xdr())])


def _patch_server(monkeypatch: pytest.MonkeyPatch, server: _VerifyServer) -> None:
    monkeypatch.setattr(settings, "contract_id", CONTRACT_ID)
    monkeypatch.setattr(soroban, "_get_server", lambda: server)


# ── verify_on_chain ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_returns_none_without_a_contract(monkeypatch):
    """Nothing is deployed, so there is nothing to ask — and no call is made."""
    monkeypatch.setattr(settings, "contract_id", "")
    server = _VerifyServer(_result(scval.to_bytes(b"x" * 32)))
    monkeypatch.setattr(soroban, "_get_server", lambda: server)

    assert await soroban.verify_on_chain(DATASET_HASH) is None
    assert server.call_count == 0


@pytest.mark.asyncio
async def test_verify_returns_none_when_the_rpc_is_unreachable(monkeypatch):
    """An unreachable RPC is "could not check", not "not anchored"."""
    _patch_server(monkeypatch, _VerifyServer(raises=RuntimeError("connection reset")))

    assert await soroban.verify_on_chain(DATASET_HASH) is None


@pytest.mark.asyncio
async def test_verify_returns_none_on_a_simulation_error(monkeypatch):
    _patch_server(monkeypatch, _VerifyServer(_Simulation(error="Error(Contract, #7)")))

    assert await soroban.verify_on_chain(DATASET_HASH) is None


@pytest.mark.asyncio
async def test_verify_returns_none_when_there_are_no_results(monkeypatch):
    _patch_server(monkeypatch, _VerifyServer(_Simulation()))

    assert await soroban.verify_on_chain(DATASET_HASH) is None


@pytest.mark.asyncio
async def test_verify_returns_none_for_a_void_result(monkeypatch):
    """The contract serializes ``Option::None`` as SCV_VOID: no such record."""
    _patch_server(monkeypatch, _VerifyServer(_result(scval.to_void())))

    assert await soroban.verify_on_chain(DATASET_HASH) is None


@pytest.mark.asyncio
async def test_verify_returns_none_for_an_unparseable_result(monkeypatch):
    """Malformed result XDR must not raise out of a read path."""
    _patch_server(monkeypatch, _VerifyServer(_Simulation(results=[_Result("not-xdr")])))

    assert await soroban.verify_on_chain(DATASET_HASH) is None


@pytest.mark.asyncio
async def test_verify_returns_none_when_the_record_cannot_be_decoded(monkeypatch):
    """A decoded SCVal that is not a record is a miss, not an exception."""

    def _undecodable(_value):
        raise ValueError("unsupported SCVal")

    monkeypatch.setattr(soroban.scval, "to_native", _undecodable)
    _patch_server(monkeypatch, _VerifyServer(_result(scval.to_bytes(b"x" * 32))))

    assert await soroban.verify_on_chain(DATASET_HASH) is None


@pytest.mark.asyncio
async def test_verify_returns_a_json_safe_record(monkeypatch):
    """BytesN<32> becomes hex and the Address submitter becomes its StrKey."""
    submitter = Keypair.random().public_key
    record = scval.to_struct(
        {
            "dataset_hash": scval.to_bytes(bytes.fromhex(DATASET_HASH)),
            "anomaly_score": scval.to_uint32(4200),
            "model_version": scval.to_symbol("isoforest_v1"),
            "submitter": scval.to_address(submitter),
        }
    )
    _patch_server(monkeypatch, _VerifyServer(_result(record)))

    result = await soroban.verify_on_chain(DATASET_HASH)

    assert result is not None
    assert result["dataset_hash"] == DATASET_HASH
    assert result["anomaly_score"] == 4200
    assert result["model_version"] == "isoforest_v1"
    # The clean G... address, never the SDK's `<Address ...>` repr.
    assert result["submitter"] == submitter


@pytest.mark.asyncio
async def test_verify_hexes_a_bytes_submitter(monkeypatch):
    """A submitter that decodes to raw bytes is hexed for the response."""
    record = scval.to_struct(
        {
            "dataset_hash": scval.to_bytes(bytes.fromhex(DATASET_HASH)),
            "submitter": scval.to_bytes(b"\x01\x02"),
        }
    )
    _patch_server(monkeypatch, _VerifyServer(_result(record)))

    result = await soroban.verify_on_chain(DATASET_HASH)

    assert result is not None
    assert result["submitter"] == "0102"


@pytest.mark.asyncio
async def test_verify_stringifies_a_non_string_submitter(monkeypatch):
    """Anything else still has to leave the handler as JSON-serializable."""
    record = scval.to_struct({"submitter": scval.to_uint32(7)})
    _patch_server(monkeypatch, _VerifyServer(_result(record)))

    result = await soroban.verify_on_chain(DATASET_HASH)

    assert result is not None
    assert result["submitter"] == "7"


# ── verify_inclusion_on_chain ─────────────────────────────────────


@pytest.mark.asyncio
async def test_inclusion_returns_none_without_a_contract(monkeypatch):
    monkeypatch.setattr(settings, "contract_id", "")

    assert await soroban.verify_inclusion_on_chain(MERKLE_ROOT, DATASET_HASH, 0, []) is None


@pytest.mark.asyncio
async def test_inclusion_returns_none_when_the_rpc_is_unreachable(monkeypatch):
    _patch_server(monkeypatch, _VerifyServer(raises=RuntimeError("connection reset")))

    assert await soroban.verify_inclusion_on_chain(MERKLE_ROOT, DATASET_HASH, 0, []) is None


@pytest.mark.asyncio
async def test_inclusion_returns_none_on_a_simulation_error(monkeypatch):
    _patch_server(monkeypatch, _VerifyServer(_Simulation(error="Error(Contract, #7)")))

    assert await soroban.verify_inclusion_on_chain(MERKLE_ROOT, DATASET_HASH, 0, []) is None


@pytest.mark.asyncio
async def test_inclusion_returns_none_when_there_are_no_results(monkeypatch):
    _patch_server(monkeypatch, _VerifyServer(_Simulation()))

    assert await soroban.verify_inclusion_on_chain(MERKLE_ROOT, DATASET_HASH, 0, []) is None


@pytest.mark.asyncio
async def test_inclusion_returns_none_for_an_unparseable_result(monkeypatch):
    _patch_server(monkeypatch, _VerifyServer(_Simulation(results=[_Result("not-xdr")])))

    assert await soroban.verify_inclusion_on_chain(MERKLE_ROOT, DATASET_HASH, 0, []) is None


@pytest.mark.asyncio
async def test_inclusion_accepts_a_valid_proof(monkeypatch):
    """The proof is passed through with its siblings and the contract says yes."""
    _patch_server(monkeypatch, _VerifyServer(_result(scval.to_bool(True))))

    assert (
        await soroban.verify_inclusion_on_chain(MERKLE_ROOT, DATASET_HASH, 1, ["ef" * 32]) is True
    )


@pytest.mark.asyncio
async def test_inclusion_rejects_a_wrong_proof(monkeypatch):
    """A contract "no" stays a definite ``False``, distinct from ``None``."""
    _patch_server(monkeypatch, _VerifyServer(_result(scval.to_bool(False))))

    assert (
        await soroban.verify_inclusion_on_chain(MERKLE_ROOT, DATASET_HASH, 1, ["ef" * 32]) is False
    )


@pytest.mark.asyncio
async def test_inclusion_returns_none_for_a_non_boolean_result(monkeypatch):
    """Only a real boolean counts as a verdict."""
    _patch_server(monkeypatch, _VerifyServer(_result(scval.to_uint32(1))))

    assert await soroban.verify_inclusion_on_chain(MERKLE_ROOT, DATASET_HASH, 0, []) is None
