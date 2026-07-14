"""Integration tests for dataset API endpoints.

Uses an in-memory SQLite database and mocks the Soroban RPC client
so tests run quickly without external network calls.
"""

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import (
    ANOMALOUS_CSV,
    MOCK_LEDGER,
    MOCK_TX_HASH,
    SAMPLE_CSV,
    SAMPLE_JSON,
    SAMPLE_JSON_WRAPPED,
)

TEST_ADDRESS = "GABCDEF123456789012345678901234567890123"


# ── POST /api/v1/datasets ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_dataset_success(client: AsyncClient, mock_build_transaction):
    """Happy path: upload a valid CSV and get back a dataset response."""
    response = await client.post(
        "/api/v1/datasets",
        data={"submitter_address": TEST_ADDRESS},
        files={"file": ("test.csv", SAMPLE_CSV, "text/csv")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["dataset_id"] is not None
    assert data["dataset_hash"] is not None
    assert len(data["dataset_hash"]) == 64  # SHA-256 hex
    assert data["unsigned_transaction_xdr"] is not None
    assert data["anomaly_report"]["score"] is not None
    assert data["anomaly_report"]["model_version"] == "isoforest_v1"


@pytest.mark.asyncio
async def test_create_dataset_rejects_unsupported_format(client: AsyncClient):
    """Upload a non-CSV/non-JSON file should return 400."""
    response = await client.post(
        "/api/v1/datasets",
        data={"submitter_address": TEST_ADDRESS},
        files={"file": ("test.txt", b"not csv", "text/plain")},
    )
    assert response.status_code == 400
    assert "csv" in response.json()["detail"].lower() or "json" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_dataset_rejects_missing_extension(client: AsyncClient):
    """Upload a file with no extension should return 400."""
    response = await client.post(
        "/api/v1/datasets",
        data={"submitter_address": TEST_ADDRESS},
        files={"file": ("test", b"some data", "application/octet-stream")},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_dataset_rejects_invalid_address(client: AsyncClient):
    """Upload with an invalid Stellar address should return 400."""
    response = await client.post(
        "/api/v1/datasets",
        data={"submitter_address": "XINVALID"},
        files={"file": ("test.csv", SAMPLE_CSV, "text/csv")},
    )
    assert response.status_code == 400
    assert "Stellar" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_dataset_empty_csv(client: AsyncClient):
    """Upload an empty CSV should return 400."""
    response = await client.post(
        "/api/v1/datasets",
        data={"submitter_address": TEST_ADDRESS},
        files={"file": ("test.csv", b"", "text/csv")},
    )
    assert response.status_code == 400
    # The CSV parser will fail because there are no columns to parse
    assert (
        "parse" in response.json()["detail"].lower() or "empty" in response.json()["detail"].lower()
    )


@pytest.mark.asyncio
async def test_create_dataset_with_anomalies(client: AsyncClient, mock_build_transaction):
    """Upload a CSV with anomalous values should produce a non-zero anomaly score.

    1 anomalous row out of 6 yields ~16.7% score, which maps to "SUSPECT" label
    (between 5% and 20% threshold).
    """
    response = await client.post(
        "/api/v1/datasets",
        data={"submitter_address": TEST_ADDRESS},
        files={"file": ("anomalous.csv", ANOMALOUS_CSV, "text/csv")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["anomaly_report"]["score"] > 0
    assert len(data["anomaly_report"]["flags"]) > 0
    # ~16.7% score is below 20% threshold, so label is SUSPECT
    assert "SUSPECT" in data["anomaly_report"]["summary"]
    assert (
        "16.7" in data["anomaly_report"]["summary"] or "16.6" in data["anomaly_report"]["summary"]
    )


# ── POST /api/v1/datasets/{id}/submit ────────────────────────────


@pytest.mark.asyncio
async def test_submit_dataset_success(
    client: AsyncClient, mock_build_transaction, mock_submit_transaction
):
    """Submit a signed transaction for a previously created dataset."""
    # First create a dataset
    create_resp = await client.post(
        "/api/v1/datasets",
        data={"submitter_address": TEST_ADDRESS},
        files={"file": ("test.csv", SAMPLE_CSV, "text/csv")},
    )
    dataset_id = create_resp.json()["dataset_id"]

    # Now submit it
    response = await client.post(
        f"/api/v1/datasets/{dataset_id}/submit",
        json={"signed_transaction_xdr": "AAAAAgAAAABtest..."},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "anchored"
    assert data["stellar_tx_hash"] == MOCK_TX_HASH
    assert data["ledger_number"] == MOCK_LEDGER
    assert "stellar.expert" in data["explorer_url"]


@pytest.mark.asyncio
async def test_submit_nonexistent_dataset(client: AsyncClient):
    """Submitting a non-existent dataset should return 404."""
    response = await client.post(
        "/api/v1/datasets/nonexistent-id/submit",
        json={"signed_transaction_xdr": "AAAA..."},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_submit_dataset_failure(
    client: AsyncClient, mock_build_transaction, mock_submit_transaction_failure
):
    """When Soroban submission fails, the dataset status should be 'failed'."""
    create_resp = await client.post(
        "/api/v1/datasets",
        data={"submitter_address": TEST_ADDRESS},
        files={"file": ("test.csv", SAMPLE_CSV, "text/csv")},
    )
    dataset_id = create_resp.json()["dataset_id"]

    response = await client.post(
        f"/api/v1/datasets/{dataset_id}/submit",
        json={"signed_transaction_xdr": "AAAA..."},
    )
    assert response.status_code == 502  # Bad Gateway
    assert "Soroban" in response.json()["detail"]


# ── GET /api/v1/datasets ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_datasets_empty(client: AsyncClient):
    """Initially the dataset list should be empty."""
    response = await client.get("/api/v1/datasets")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["datasets"] == []


@pytest.mark.asyncio
async def test_list_datasets_with_data(
    client: AsyncClient, mock_build_transaction, mock_submit_transaction
):
    """After creating and submitting datasets, they should appear in the list."""
    # Create and submit two datasets with different content to avoid hash collision.
    # Must have 2+ numeric feature columns (lat/long are dropped, sample_id is dropped).
    csv1 = f"sample_id,latitude,longitude,ph,conductivity\nA,0.0,0.0,7.2,450.0\n# {uuid.uuid4()}"
    csv2 = f"sample_id,latitude,longitude,ph,conductivity\nB,0.0,0.0,8.1,999.0\n# {uuid.uuid4()}"
    for csv_content in [csv1, csv2]:
        create_resp = await client.post(
            "/api/v1/datasets",
            data={"submitter_address": TEST_ADDRESS},
            files={"file": ("test.csv", csv_content, "text/csv")},
        )
        ds_id = create_resp.json()["dataset_id"]
        await client.post(
            f"/api/v1/datasets/{ds_id}/submit",
            json={"signed_transaction_xdr": "AAAA..."},
        )

    response = await client.get("/api/v1/datasets")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["datasets"]) == 2
    for ds in data["datasets"]:
        assert "dataset_id" in ds
        assert "dataset_hash" in ds
        assert "status" in ds


# ── GET /api/v1/datasets/{id} ─────────────────────────────────────


@pytest.mark.asyncio
async def test_get_dataset_by_id(client: AsyncClient, mock_build_transaction):
    """Fetch a single dataset by its ID."""
    create_resp = await client.post(
        "/api/v1/datasets",
        data={"submitter_address": TEST_ADDRESS},
        files={"file": ("test.csv", SAMPLE_CSV, "text/csv")},
    )
    dataset_id = create_resp.json()["dataset_id"]

    response = await client.get(f"/api/v1/datasets/{dataset_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["dataset_id"] == dataset_id
    assert data["dataset_hash"] is not None
    assert data["status"] == "pending"
    assert data["anomaly_score"] is not None


@pytest.mark.asyncio
async def test_get_dataset_not_found(client: AsyncClient):
    """Fetch a non-existent dataset should return 404."""
    response = await client.get("/api/v1/datasets/nonexistent-id")
    assert response.status_code == 404


# ── GET /api/v1/health ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    """Health check should return ok."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


# ── JSON upload tests ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_dataset_json_success(client: AsyncClient, mock_build_transaction):
    """Happy path: upload a valid JSON file and get back a dataset response."""
    response = await client.post(
        "/api/v1/datasets",
        data={"submitter_address": TEST_ADDRESS},
        files={"file": ("test.json", SAMPLE_JSON, "application/json")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["dataset_id"] is not None
    assert data["dataset_hash"] is not None
    assert len(data["dataset_hash"]) == 64  # SHA-256 hex
    assert data["unsigned_transaction_xdr"] is not None
    assert data["anomaly_report"]["score"] is not None
    assert data["anomaly_report"]["model_version"] == "isoforest_v1"


@pytest.mark.asyncio
async def test_create_dataset_json_wrapped_success(client: AsyncClient, mock_build_transaction):
    """Upload JSON wrapped in {"data": [...]} should also succeed."""
    response = await client.post(
        "/api/v1/datasets",
        data={"submitter_address": TEST_ADDRESS},
        files={"file": ("test.json", SAMPLE_JSON_WRAPPED, "application/json")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["dataset_hash"] is not None
    assert len(data["dataset_hash"]) == 64


@pytest.mark.asyncio
async def test_create_dataset_json_invalid_structure(client: AsyncClient):
    """Upload malformed JSON should return 400."""
    response = await client.post(
        "/api/v1/datasets",
        data={"submitter_address": TEST_ADDRESS},
        files={"file": ("test.json", b'{"not": "an array"}', "application/json")},
    )
    assert response.status_code == 400
    assert "array" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_dataset_json_syntax_error(client: AsyncClient):
    """Upload invalid JSON syntax should return 400."""
    response = await client.post(
        "/api/v1/datasets",
        data={"submitter_address": TEST_ADDRESS},
        files={"file": ("test.json", b"not valid json", "application/json")},
    )
    assert response.status_code == 400
    assert "JSON" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_dataset_json_empty_array(client: AsyncClient):
    """Upload an empty JSON array should return 400."""
    response = await client.post(
        "/api/v1/datasets",
        data={"submitter_address": TEST_ADDRESS},
        files={"file": ("test.json", b"[]", "application/json")},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_dataset_json_with_anomalies(client: AsyncClient, mock_build_transaction):
    """Upload JSON with a clear outlier row should produce non-zero anomaly score."""
    anomalous_json = """[
      {"conductivity": 450.0, "dissolved_oxygen": 8.5, "pH": 7.2, "temperature": 22.1},
      {"conductivity": 452.0, "dissolved_oxygen": 8.3, "pH": 7.15, "temperature": 22.3},
      {"conductivity": 448.0, "dissolved_oxygen": 8.7, "pH": 7.18, "temperature": 22.0},
      {"conductivity": 455.0, "dissolved_oxygen": 8.4, "pH": 7.22, "temperature": 22.2},
      {"conductivity": 449.0, "dissolved_oxygen": 8.6, "pH": 7.19, "temperature": 22.4},
      {"conductivity": 9999.0, "dissolved_oxygen": 0.1, "pH": 9.99, "temperature": 999.99}
    ]"""
    response = await client.post(
        "/api/v1/datasets",
        data={"submitter_address": TEST_ADDRESS},
        files={"file": ("test.json", anomalous_json, "application/json")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["anomaly_report"]["score"] > 0
    assert len(data["anomaly_report"]["flags"]) > 0


@pytest.mark.asyncio
async def test_create_dataset_json_not_utf8(client: AsyncClient):
    """Upload non-UTF-8 JSON should return 400."""
    # Latin-1 encoded data that is not valid UTF-8
    response = await client.post(
        "/api/v1/datasets",
        data={"submitter_address": TEST_ADDRESS},
        files={"file": ("test.json", b"\xff\xfe\x00\x01", "application/json")},
    )
    assert response.status_code == 400
    detail = response.json()["detail"].lower()
    assert "utf-8" in detail or "utf" in detail
