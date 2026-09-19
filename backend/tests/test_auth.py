"""Tests for API-key authentication on the write endpoints.

The API starts with authentication disabled (no ``API_KEYS`` configured) so a
local checkout runs without setup. These tests characterize that dev behaviour:
upload and anchor calls succeed without a header. Once keys are configured,
every write endpoint must refuse an unauthenticated caller, while verification
and health stay public.
"""

import pytest
from httpx import AsyncClient

from tests.conftest import unique_sample_csv

TEST_ADDRESS = "GABCDEF123456789012345678901234567890123"


async def upload(client: AsyncClient):
    """POST an upload and return the response."""
    return await client.post(
        "/api/v1/datasets",
        files={"file": ("test.csv", unique_sample_csv(), "text/csv")},
    )


# ── Dev default: authentication disabled ──────────────────────────


@pytest.mark.asyncio
async def test_upload_and_anchor_are_open_without_keys(
    client: AsyncClient, mock_build_transaction
) -> None:
    """With no keys configured, the upload and anchor steps accept anonymous calls."""
    created = await upload(client)
    assert created.status_code == 201, created.text

    anchored = await client.post(
        f"/api/v1/datasets/{created.json()['dataset_id']}/anchor",
        json={"submitter_address": TEST_ADDRESS},
    )
    assert anchored.status_code == 200, anchored.text


@pytest.mark.asyncio
async def test_batch_writes_are_open_without_keys(
    client: AsyncClient, mock_build_root_transaction
) -> None:
    """Batch creation is open too while auth is disabled."""
    created = await upload(client)
    created_id = created.json()["dataset_id"]

    batch = await client.post(
        "/api/v1/batches",
        json={"submitter_address": TEST_ADDRESS, "dataset_ids": [created_id]},
    )
    assert batch.status_code == 201, batch.text
