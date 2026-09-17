"""Tests for the maintenance endpoints and the anchoring/renewal seams.

The status endpoint is how an operator notices that TTL renewal has stopped
working, so these tests check it reports real counts, and that both anchoring
paths leave the renewal job a deadline to beat.
"""

import secrets
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.models.batch import Batch
from app.models.dataset import Dataset
from app.services.ttl_renewal import ensure_utc
from tests.conftest import TestSessionLocal, analyze_and_anchor

TEST_ADDRESS = "GABCDEF123456789012345678901234567890123"

SAMPLE_CSV = (
    "sample_id,latitude,longitude,pH,conductivity\n"
    "S001,34.05,-118.24,7.2,450.0\n"
    "S002,34.06,-118.25,7.3,451.0\n"
)

MOCK_SIGNED_XDR = "AAAAAgAAAABbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


async def _seed_root(expires_in: timedelta | None) -> str:
    """Insert an anchored batch so the endpoint has something to count."""
    batch_id = str(uuid.uuid4())
    moment = datetime.now(UTC)

    async with TestSessionLocal() as db:
        db.add(
            Batch(
                batch_id=batch_id,
                submitter_address=TEST_ADDRESS,
                merkle_root=secrets.token_hex(32),
                leaf_count=1,
                status="anchored",
                anchored_at=moment,
                root_ttl_expires_at=None if expires_in is None else moment + expires_in,
            )
        )
        await db.commit()

    return batch_id


# ── GET /api/v1/maintenance/ttl-status ────────────────────────────


@pytest.mark.asyncio
async def test_ttl_status_is_valid_with_no_entries(client: AsyncClient):
    response = await client.get("/api/v1/maintenance/ttl-status")

    assert response.status_code == 200
    body = response.json()
    assert body["roots"]["anchored"] == 0
    assert body["records"]["anchored"] == 0
    assert body["roots"]["due_for_renewal"] == 0
    assert body["records"]["due_for_renewal"] == 0


@pytest.mark.asyncio
async def test_ttl_status_counts_roots_by_urgency(client: AsyncClient):
    await _seed_root(timedelta(days=1))
    await _seed_root(timedelta(days=200))
    await _seed_root(timedelta(days=-3))
    await _seed_root(None)

    roots = (await client.get("/api/v1/maintenance/ttl-status")).json()["roots"]

    assert roots["anchored"] == 4
    assert roots["due_for_renewal"] == 2
    assert roots["past_recorded_expiry"] == 1
    assert roots["without_recorded_expiry"] == 1


@pytest.mark.asyncio
async def test_ttl_status_advertises_the_lifetime_it_renews_to(client: AsyncClient):
    body = (await client.get("/api/v1/maintenance/ttl-status")).json()

    assert body["entry_lifetime_days"] == 180.0
    assert body["renewal_window_days"] == 30


# ── Anchoring leaves the job a deadline ───────────────────────────


@pytest.mark.asyncio
async def test_anchoring_a_dataset_records_its_record_ttl_deadline(
    client: AsyncClient,
    mock_build_transaction,
    mock_submit_transaction,
):
    """Without a recorded deadline a standalone record is never selected.

    That is the default upload path, so a missing deadline here would mean the
    common case expires unnoticed while only batching gets renewed.
    """
    dataset = await analyze_and_anchor(client, TEST_ADDRESS, SAMPLE_CSV, "samples.csv")
    dataset_id = dataset["dataset_id"]

    submitted = await client.post(
        f"/api/v1/datasets/{dataset_id}/submit",
        json={"signed_transaction_xdr": MOCK_SIGNED_XDR},
    )
    assert submitted.status_code == 200, submitted.text

    async with TestSessionLocal() as db:
        dataset = await db.get(Dataset, dataset_id)

    assert dataset is not None
    assert dataset.anchored_at is not None
    assert ensure_utc(dataset.ttl_expires_at) == ensure_utc(dataset.anchored_at) + timedelta(
        days=180
    )
    assert dataset.ttl_renewal_attempts == 0
    assert dataset.last_ttl_renewed_at is None


@pytest.mark.asyncio
async def test_a_standalone_dataset_shows_up_as_healthy(
    client: AsyncClient,
    mock_build_transaction,
    mock_submit_transaction,
):
    """A freshly anchored record has ~180 days left, so nothing is due yet."""
    dataset = await analyze_and_anchor(client, TEST_ADDRESS, SAMPLE_CSV, "samples.csv")
    dataset_id = dataset["dataset_id"]
    await client.post(
        f"/api/v1/datasets/{dataset_id}/submit",
        json={"signed_transaction_xdr": MOCK_SIGNED_XDR},
    )

    records = (await client.get("/api/v1/maintenance/ttl-status")).json()["records"]

    assert records["anchored"] == 1
    assert records["due_for_renewal"] == 0
    assert records["past_recorded_expiry"] == 0
    assert records["with_renewal_error"] == 0
    assert records["next_expiry_at"] is not None


@pytest.mark.asyncio
async def test_anchoring_a_batch_records_its_root_ttl_deadline(
    client: AsyncClient,
    mock_build_transaction,
    mock_build_root_transaction,
    mock_submit_batch_transaction,
):
    upload = await client.post(
        "/api/v1/datasets",
        files={"file": ("samples.csv", SAMPLE_CSV, "text/csv")},
    )
    assert upload.status_code == 201, upload.text
    dataset_id = upload.json()["dataset_id"]

    created = await client.post(
        "/api/v1/batches",
        json={"submitter_address": TEST_ADDRESS, "dataset_ids": [dataset_id]},
    )
    assert created.status_code == 201, created.text
    batch_id = created.json()["batch_id"]

    submitted = await client.post(
        f"/api/v1/batches/{batch_id}/submit",
        json={"signed_transaction_xdr": MOCK_SIGNED_XDR},
    )
    assert submitted.status_code == 200, submitted.text

    async with TestSessionLocal() as db:
        batch = await db.get(Batch, batch_id)
        dataset = await db.get(Dataset, dataset_id)

    assert batch is not None
    assert batch.anchored_at is not None
    assert ensure_utc(batch.root_ttl_expires_at) == ensure_utc(batch.anchored_at) + timedelta(
        days=180
    )
    assert batch.ttl_renewal_attempts == 0

    # A batched dataset is covered by its batch root, so it must carry no record
    # deadline of its own — renewing one would fail on-chain with HashNotFound.
    assert dataset is not None
    assert dataset.batch_id == batch_id
    assert dataset.ttl_expires_at is None


@pytest.mark.asyncio
async def test_a_batched_dataset_is_not_reported_as_an_expiring_record(
    client: AsyncClient,
    mock_build_transaction,
    mock_build_root_transaction,
    mock_submit_batch_transaction,
):
    upload = await client.post(
        "/api/v1/datasets",
        files={"file": ("samples.csv", SAMPLE_CSV, "text/csv")},
    )
    dataset_id = upload.json()["dataset_id"]
    created = await client.post(
        "/api/v1/batches",
        json={"submitter_address": TEST_ADDRESS, "dataset_ids": [dataset_id]},
    )
    batch_id = created.json()["batch_id"]
    await client.post(
        f"/api/v1/batches/{batch_id}/submit",
        json={"signed_transaction_xdr": MOCK_SIGNED_XDR},
    )

    body = (await client.get("/api/v1/maintenance/ttl-status")).json()

    assert body["roots"]["anchored"] == 1
    assert body["records"]["anchored"] == 0
