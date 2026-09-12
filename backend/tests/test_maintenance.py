"""Tests for the maintenance endpoints and the anchoring/renewal seam.

The status endpoint is how an operator notices that root renewal has stopped
working, so these tests check it reports real counts and that anchoring a batch
actually leaves the renewal job a deadline to beat.
"""

import secrets
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.models.batch import Batch
from app.services.ttl_renewal import ensure_utc
from tests.conftest import TestSessionLocal

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
async def test_ttl_status_is_valid_with_no_roots(client: AsyncClient):
    response = await client.get("/api/v1/maintenance/ttl-status")

    assert response.status_code == 200
    body = response.json()
    assert body["anchored_roots"] == 0
    assert body["roots_due_for_renewal"] == 0
    assert body["next_expiry_at"] is None


@pytest.mark.asyncio
async def test_ttl_status_counts_roots_by_urgency(client: AsyncClient):
    await _seed_root(timedelta(days=1))
    await _seed_root(timedelta(days=200))
    await _seed_root(timedelta(days=-3))
    await _seed_root(None)

    body = (await client.get("/api/v1/maintenance/ttl-status")).json()

    assert body["anchored_roots"] == 4
    assert body["roots_due_for_renewal"] == 2
    assert body["roots_past_recorded_expiry"] == 1
    assert body["roots_without_recorded_expiry"] == 1


@pytest.mark.asyncio
async def test_ttl_status_advertises_the_lifetime_it_renews_to(client: AsyncClient):
    body = (await client.get("/api/v1/maintenance/ttl-status")).json()

    assert body["root_lifetime_days"] == 180.0
    assert body["renewal_window_days"] == 30


# ── Anchoring leaves the job a deadline ───────────────────────────


@pytest.mark.asyncio
async def test_anchoring_a_batch_records_its_ttl_deadline(
    client: AsyncClient,
    mock_build_transaction,
    mock_build_root_transaction,
    mock_submit_batch_transaction,
):
    """Without a recorded deadline a root is never selected, so it would expire silently."""
    upload = await client.post(
        "/api/v1/datasets",
        data={"submitter_address": TEST_ADDRESS},
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

    assert batch is not None
    assert batch.anchored_at is not None
    # The contract bumps a new root to its full TTL budget on write, so the
    # deadline the job works against is that budget after the anchor time.
    assert ensure_utc(batch.root_ttl_expires_at) == ensure_utc(batch.anchored_at) + timedelta(
        days=180
    )
    assert batch.ttl_renewal_attempts == 0
    assert batch.last_ttl_renewed_at is None


@pytest.mark.asyncio
async def test_an_anchored_root_is_visible_as_healthy(
    client: AsyncClient,
    mock_build_transaction,
    mock_build_root_transaction,
    mock_submit_batch_transaction,
):
    """A freshly anchored batch has ~180 days left, so nothing is due for renewal."""
    upload = await client.post(
        "/api/v1/datasets",
        data={"submitter_address": TEST_ADDRESS},
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

    assert body["anchored_roots"] == 1
    assert body["roots_due_for_renewal"] == 0
    assert body["roots_past_recorded_expiry"] == 0
    assert body["roots_with_renewal_error"] == 0
    assert body["next_expiry_at"] is not None
