"""Integration tests for the Merkle batch anchoring API.

Uses the in-memory SQLite database and mocked Soroban RPC from ``conftest``.
"""

import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.config import settings
from app.core.exceptions import AnchorAlreadyExistsError
from app.models.dataset import Dataset
from app.services import merkle
from tests.conftest import MOCK_LEDGER, MOCK_TX_HASH, TestSessionLocal, anchor

TEST_ADDRESS = "GABCDEF123456789012345678901234567890123"
OTHER_ADDRESS = "G" + "B" * 55


def _csv(tag: str, ph: float = 7.2) -> str:
    """Build a small, unique geochemical CSV so each dataset hashes differently."""
    return (
        "sample_id,latitude,longitude,pH,conductivity\n"
        f"S001,34.05,-118.24,{ph},450.0\n"
        f"S002,34.06,-118.25,{ph + 0.1},451.0\n"
        f"S003,34.07,-118.26,{ph + 0.2},452.0\n"
        f"# {tag}\n"
    )


async def _create_dataset(client: AsyncClient, tag: str, ph: float = 7.2) -> dict:
    """Analyze an upload through the real endpoint and return its response.

    No address is involved: batching is what binds one, so calling this leaves
    the dataset unclaimed unless a test anchors it explicitly.
    """
    resp = await client.post(
        "/api/v1/datasets",
        files={"file": (f"{tag}.csv", _csv(tag, ph), "text/csv")},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_batch(client: AsyncClient, dataset_ids: list[str]) -> dict:
    resp = await client.post(
        "/api/v1/batches",
        json={"submitter_address": TEST_ADDRESS, "dataset_ids": dataset_ids},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── POST /api/v1/batches ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_batch_success(
    client: AsyncClient,
    mock_build_transaction,
    mock_build_root_transaction,
):
    """A batch commits every requested dataset to one root and returns its proofs."""
    first = await _create_dataset(client, "batch-a")
    second = await _create_dataset(client, "batch-b")

    batch = await _create_batch(client, [first["dataset_id"], second["dataset_id"]])

    assert len(batch["merkle_root"]) == 64
    assert batch["leaf_count"] == 2
    assert batch["unsigned_transaction_xdr"]
    assert [leaf["dataset_id"] for leaf in batch["leaves"]] == [
        first["dataset_id"],
        second["dataset_id"],
    ]

    # Every returned proof must reconstruct the anchored root.
    for leaf in batch["leaves"]:
        assert merkle.verify_proof(
            leaf["dataset_hash"],
            leaf["leaf_index"],
            leaf["merkle_proof"],
            batch["merkle_root"],
        )

    # The root is genuinely derived from the dataset hashes.
    assert batch["merkle_root"] == merkle.compute_root(
        [first["dataset_hash"], second["dataset_hash"]]
    )


@pytest.mark.asyncio
async def test_create_batch_follows_requested_leaf_order(
    client: AsyncClient,
    mock_build_transaction,
    mock_build_root_transaction,
):
    """Leaf order comes from dataset_ids, not from insertion order."""
    a = await _create_dataset(client, "order-a")
    b = await _create_dataset(client, "order-b")

    batch = await _create_batch(client, [b["dataset_id"], a["dataset_id"]])

    assert [leaf["dataset_id"] for leaf in batch["leaves"]] == [b["dataset_id"], a["dataset_id"]]
    assert [leaf["leaf_index"] for leaf in batch["leaves"]] == [0, 1]
    # Reversing the order changes the root, which is why order is pinned.
    assert batch["merkle_root"] == merkle.compute_root([b["dataset_hash"], a["dataset_hash"]])


@pytest.mark.asyncio
async def test_create_batch_stores_membership_on_datasets(
    client: AsyncClient,
    mock_build_transaction,
    mock_build_root_transaction,
):
    """Each dataset records its batch, leaf index, root, and proof."""
    dataset = await _create_dataset(client, "membership")
    batch = await _create_batch(client, [dataset["dataset_id"]])

    resp = await client.get(f"/api/v1/datasets/{dataset['dataset_id']}")
    assert resp.status_code == 200
    stored = resp.json()

    assert stored["batch_id"] == batch["batch_id"]
    assert stored["merkle_root"] == batch["merkle_root"]
    assert stored["leaf_index"] == 0
    assert stored["merkle_proof"] == []


@pytest.mark.asyncio
async def test_create_batch_rejects_duplicate_ids(
    client: AsyncClient,
    mock_build_transaction,
    mock_build_root_transaction,
):
    dataset = await _create_dataset(client, "dupe")

    resp = await client.post(
        "/api/v1/batches",
        json={
            "submitter_address": TEST_ADDRESS,
            "dataset_ids": [dataset["dataset_id"], dataset["dataset_id"]],
        },
    )
    assert resp.status_code == 400
    assert "duplicates" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_batch_rejects_empty_list(client: AsyncClient):
    resp = await client.post(
        "/api/v1/batches",
        json={"submitter_address": TEST_ADDRESS, "dataset_ids": []},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_batch_rejects_invalid_address(client: AsyncClient):
    resp = await client.post(
        "/api/v1/batches",
        json={"submitter_address": "XINVALID", "dataset_ids": ["anything"]},
    )
    assert resp.status_code == 400
    assert "Stellar" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_batch_rejects_unknown_dataset(
    client: AsyncClient,
    mock_build_transaction,
    mock_build_root_transaction,
):
    dataset = await _create_dataset(client, "unknown")

    resp = await client.post(
        "/api/v1/batches",
        json={
            "submitter_address": TEST_ADDRESS,
            "dataset_ids": [dataset["dataset_id"], "does-not-exist"],
        },
    )
    assert resp.status_code == 404
    assert "does-not-exist" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_batch_rejects_another_addresses_dataset(
    client: AsyncClient,
    mock_build_transaction,
    mock_build_root_transaction,
):
    dataset = await _create_dataset(client, "foreign")
    # Bind an owner first: only a dataset that already belongs to somebody can
    # be refused to somebody else.
    await anchor(client, dataset["dataset_id"], TEST_ADDRESS)

    resp = await client.post(
        "/api/v1/batches",
        json={"submitter_address": OTHER_ADDRESS, "dataset_ids": [dataset["dataset_id"]]},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_batch_claims_a_dataset_that_has_no_submitter_yet(
    client: AsyncClient,
    mock_build_transaction,
    mock_build_root_transaction,
):
    """Batching is what binds an address to a dataset that was only analyzed."""
    dataset = await _create_dataset(client, "unclaimed")

    resp = await client.post(
        "/api/v1/batches",
        json={"submitter_address": TEST_ADDRESS, "dataset_ids": [dataset["dataset_id"]]},
    )
    assert resp.status_code == 201, resp.text

    async with TestSessionLocal() as db:
        stored = await db.get(Dataset, dataset["dataset_id"])

    assert stored is not None
    assert stored.submitter_address == TEST_ADDRESS


@pytest.mark.asyncio
async def test_create_batch_rejects_already_batched_dataset(
    client: AsyncClient,
    mock_build_transaction,
    mock_build_root_transaction,
):
    dataset = await _create_dataset(client, "reuse")
    await _create_batch(client, [dataset["dataset_id"]])

    resp = await client.post(
        "/api/v1/batches",
        json={"submitter_address": TEST_ADDRESS, "dataset_ids": [dataset["dataset_id"]]},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_batch_reports_an_already_anchored_root(client: AsyncClient):
    """A root the ledger already holds is a 409, and no half-written batch is left.

    The batch is persisted only after the unsigned transaction is built, so a
    duplicate root has to fail as a conflict the caller can act on while leaving
    nothing behind for a later listing to pick up.
    """
    dataset = await _create_dataset(client, "existing-root")

    with patch(
        "app.api.v1.batches.build_anchor_root_transaction",
        side_effect=AnchorAlreadyExistsError("This Merkle root is already anchored"),
    ):
        resp = await client.post(
            "/api/v1/batches",
            json={"submitter_address": TEST_ADDRESS, "dataset_ids": [dataset["dataset_id"]]},
        )

    assert resp.status_code == 409
    assert "already anchored" in resp.json()["detail"]

    listed = await client.get("/api/v1/batches")
    assert listed.json()["total"] == 0


@pytest.mark.asyncio
async def test_create_batch_enforces_size_limit(
    client: AsyncClient,
    mock_build_transaction,
    mock_build_root_transaction,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "max_batch_size", 1)
    a = await _create_dataset(client, "limit-a")
    b = await _create_dataset(client, "limit-b")

    resp = await client.post(
        "/api/v1/batches",
        json={"submitter_address": TEST_ADDRESS, "dataset_ids": [a["dataset_id"], b["dataset_id"]]},
    )
    assert resp.status_code == 400
    assert "at most 1" in resp.json()["detail"]


# ── POST /api/v1/batches/{id}/submit ──────────────────────────────


@pytest.mark.asyncio
async def test_submit_batch_anchors_every_member(
    client: AsyncClient,
    mock_build_transaction,
    mock_build_root_transaction,
    mock_submit_batch_transaction,
):
    a = await _create_dataset(client, "submit-a")
    b = await _create_dataset(client, "submit-b")
    batch = await _create_batch(client, [a["dataset_id"], b["dataset_id"]])

    resp = await client.post(
        f"/api/v1/batches/{batch['batch_id']}/submit",
        json={"signed_transaction_xdr": "AAAAAgAAAABsigned..."},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "anchored"
    assert body["stellar_tx_hash"] == MOCK_TX_HASH
    assert body["ledger_number"] == MOCK_LEDGER
    assert "stellar.expert" in body["explorer_url"]

    # Both members inherit the one transaction.
    for dataset_id in (a["dataset_id"], b["dataset_id"]):
        detail = (await client.get(f"/api/v1/datasets/{dataset_id}")).json()
        assert detail["status"] == "anchored"
        assert detail["stellar_tx_hash"] == MOCK_TX_HASH


@pytest.mark.asyncio
async def test_submit_batch_not_found(client: AsyncClient):
    resp = await client.post(
        "/api/v1/batches/nonexistent-id/submit",
        json={"signed_transaction_xdr": "AAAA..."},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_submit_batch_twice_conflicts(
    client: AsyncClient,
    mock_build_transaction,
    mock_build_root_transaction,
    mock_submit_batch_transaction,
):
    dataset = await _create_dataset(client, "twice")
    batch = await _create_batch(client, [dataset["dataset_id"]])

    payload = {"signed_transaction_xdr": "AAAA..."}
    first = await client.post(f"/api/v1/batches/{batch['batch_id']}/submit", json=payload)
    assert first.status_code == 200

    second = await client.post(f"/api/v1/batches/{batch['batch_id']}/submit", json=payload)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_submit_batch_failure_marks_batch_failed(
    client: AsyncClient,
    mock_build_transaction,
    mock_build_root_transaction,
    mock_submit_batch_transaction_failure,
):
    dataset = await _create_dataset(client, "fail")
    batch = await _create_batch(client, [dataset["dataset_id"]])

    resp = await client.post(
        f"/api/v1/batches/{batch['batch_id']}/submit",
        json={"signed_transaction_xdr": "AAAA..."},
    )
    assert resp.status_code == 502

    stored = (await client.get(f"/api/v1/batches/{batch['batch_id']}")).json()
    assert stored["status"] == "failed"
    # A failed batch must not report its datasets as anchored.
    detail = (await client.get(f"/api/v1/datasets/{dataset['dataset_id']}")).json()
    assert detail["status"] == "pending"


# ── GET /api/v1/batches ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_and_get_batches(
    client: AsyncClient,
    mock_build_transaction,
    mock_build_root_transaction,
):
    dataset = await _create_dataset(client, "list")
    batch = await _create_batch(client, [dataset["dataset_id"]])

    listed = await client.get("/api/v1/batches")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["batches"][0]["batch_id"] == batch["batch_id"]

    fetched = await client.get(f"/api/v1/batches/{batch['batch_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["merkle_root"] == batch["merkle_root"]


@pytest.mark.asyncio
async def test_get_batch_not_found(client: AsyncClient):
    resp = await client.get("/api/v1/batches/nonexistent-id")
    assert resp.status_code == 404


# ── Verification of batch membership ──────────────────────────────


@pytest.mark.asyncio
async def test_verify_reports_inclusion_for_batched_dataset(
    client: AsyncClient,
    mock_build_transaction,
    mock_build_root_transaction,
    mock_verify_inclusion_on_chain,
):
    dataset = await _create_dataset(client, "verify-batch")
    batch = await _create_batch(client, [dataset["dataset_id"]])

    resp = await client.post("/api/v1/verify", params={"dataset_id": dataset["dataset_id"]})
    assert resp.status_code == 200
    inclusion = resp.json()["inclusion"]

    assert inclusion is not None
    assert inclusion["root"] == batch["merkle_root"]
    assert inclusion["leaf_index"] == 0
    assert inclusion["proof"] == []
    assert inclusion["verified_locally"] is True
    assert inclusion["verified_on_chain"] is True


@pytest.mark.asyncio
async def test_verify_by_uploaded_file_returns_inclusion(
    client: AsyncClient,
    mock_build_transaction,
    mock_build_root_transaction,
    mock_verify_inclusion_on_chain,
):
    """Re-uploading the original CSV must surface its batch inclusion proof."""
    tag = f"reupload-{uuid.uuid4()}"
    dataset = await _create_dataset(client, tag)
    batch = await _create_batch(client, [dataset["dataset_id"]])

    resp = await client.post(
        "/api/v1/verify",
        files={"file": (f"{tag}.csv", _csv(tag), "text/csv")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["re_computed_hash"] == dataset["dataset_hash"]
    assert body["inclusion"]["root"] == batch["merkle_root"]


@pytest.mark.asyncio
async def test_verify_reports_no_inclusion_for_unbatched_dataset(
    client: AsyncClient,
    mock_build_transaction,
    mock_verify_on_chain_not_found,
):
    dataset = await _create_dataset(client, "solo")

    resp = await client.post("/api/v1/verify", params={"dataset_id": dataset["dataset_id"]})
    assert resp.status_code == 200
    assert resp.json()["inclusion"] is None
