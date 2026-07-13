"""Integration tests for the verification API endpoint."""

import pytest
from httpx import AsyncClient

from tests.conftest import SAMPLE_CSV, SAMPLE_HASH, SAMPLE_JSON

TEST_ADDRESS = "GABCDEF123456789012345678901234567890123"


# ── POST /api/v1/verify by hash ───────────────────────────────────


@pytest.mark.asyncio
async def test_verify_by_hash_found(
    client: AsyncClient,
    mock_build_transaction,
    mock_verify_on_chain_found,
):
    """Verification by hash should return match=True when the hash is on-chain."""
    response = await client.post(
        "/api/v1/verify",
        params={"dataset_hash": SAMPLE_HASH},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["match"] is True
    assert data["on_chain_record"] is not None
    assert data["on_chain_record"]["dataset_hash"] == SAMPLE_HASH


@pytest.mark.asyncio
async def test_verify_by_hash_not_found(
    client: AsyncClient,
    mock_verify_on_chain_not_found,
):
    """Verification by hash should return match=False when not on-chain."""
    response = await client.post(
        "/api/v1/verify",
        params={"dataset_hash": "a" * 64},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["match"] is False
    assert data["on_chain_record"] is None


# ── POST /api/v1/verify by dataset ID ─────────────────────────────


@pytest.mark.asyncio
async def test_verify_by_id_with_local_record(
    client: AsyncClient,
    mock_build_transaction,
    mock_verify_on_chain_not_found,
):
    """Verification by dataset ID should include local_record from DB."""
    # Create a dataset first
    create_resp = await client.post(
        "/api/v1/datasets",
        data={"submitter_address": TEST_ADDRESS},
        files={"file": ("test.csv", SAMPLE_CSV, "text/csv")},
    )
    dataset_id = create_resp.json()["dataset_id"]

    response = await client.post(
        "/api/v1/verify",
        params={"dataset_id": dataset_id},
    )
    assert response.status_code == 200
    data = response.json()
    # Even though on-chain returns None, we should have a local_record
    assert data["local_record"] is not None
    assert data["local_record"]["dataset_id"] == dataset_id


# ── POST /api/v1/verify by file upload ────────────────────────────


@pytest.mark.asyncio
async def test_verify_by_file(
    client: AsyncClient,
    mock_verify_on_chain_not_found,
):
    """Verification by file upload should re-compute the hash."""
    response = await client.post(
        "/api/v1/verify",
        files={"file": ("test.csv", SAMPLE_CSV, "text/csv")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["re_computed_hash"] is not None
    assert len(data["re_computed_hash"]) == 64  # SHA-256 hex


# ── POST /api/v1/verify — idempotent hash ─────────────────────────


@pytest.mark.asyncio
async def test_verify_hash_determinism(
    client: AsyncClient,
    mock_verify_on_chain_not_found,
):
    """The same CSV should always produce the same hash."""
    # Verify twice
    resp1 = await client.post(
        "/api/v1/verify",
        files={"file": ("test.csv", SAMPLE_CSV, "text/csv")},
    )
    resp2 = await client.post(
        "/api/v1/verify",
        files={"file": ("test.csv", SAMPLE_CSV, "text/csv")},
    )
    data1 = resp1.json()
    data2 = resp2.json()
    assert data1["re_computed_hash"] == data2["re_computed_hash"]


# ── Full integration: create → anchor → verify ────────────────────


@pytest.mark.asyncio
async def test_full_create_anchor_verify_flow(
    client: AsyncClient,
    mock_build_transaction,
    mock_submit_transaction,
    mock_verify_on_chain_found,
):
    """End-to-end: create dataset → submit → verify on-chain."""
    # Step 1: Create
    create_resp = await client.post(
        "/api/v1/datasets",
        data={"submitter_address": TEST_ADDRESS},
        files={"file": ("test.csv", SAMPLE_CSV, "text/csv")},
    )
    assert create_resp.status_code == 201
    dataset_id = create_resp.json()["dataset_id"]
    dataset_hash = create_resp.json()["dataset_hash"]

    # Step 2: Submit
    submit_resp = await client.post(
        f"/api/v1/datasets/{dataset_id}/submit",
        json={"signed_transaction_xdr": "AAAA..."},
    )
    assert submit_resp.status_code == 200
    assert submit_resp.json()["status"] == "anchored"

    # Step 3: Verify by hash
    verify_resp = await client.post(
        "/api/v1/verify",
        params={"dataset_hash": dataset_hash},
    )
    assert verify_resp.status_code == 200
    verify_data = verify_resp.json()
    assert verify_data["match"] is True
    assert verify_data["on_chain_record"] is not None

    # Step 4: Verify by dataset ID
    verify_id_resp = await client.post(
        "/api/v1/verify",
        params={"dataset_id": dataset_id},
    )
    assert verify_id_resp.status_code == 200
    verify_id_data = verify_id_resp.json()
    assert verify_id_data["local_record"] is not None
    assert verify_id_data["local_record"]["dataset_id"] == dataset_id


# ── POST /api/v1/verify by JSON file upload ───────────────────────


@pytest.mark.asyncio
async def test_verify_by_json_file(
    client: AsyncClient,
    mock_verify_on_chain_not_found,
):
    """Verification by JSON file upload should re-compute the hash."""
    response = await client.post(
        "/api/v1/verify",
        files={"file": ("test.json", SAMPLE_JSON, "application/json")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["re_computed_hash"] is not None
    assert len(data["re_computed_hash"]) == 64  # SHA-256 hex
