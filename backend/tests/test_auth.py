"""Tests for API-key authentication on the write endpoints.

The API starts with authentication disabled (no ``API_KEYS`` configured) so a
local checkout runs without setup. These tests characterize that dev behaviour:
upload and anchor calls succeed without a header. Once keys are configured,
every write endpoint must refuse an unauthenticated caller, while verification
and health stay public.
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, Response

from app.config import settings
from app.core.security import configured_api_keys
from tests.conftest import unique_sample_csv

TEST_ADDRESS = "GABCDEF123456789012345678901234567890123"
API_KEY = "test-key"


def enable_auth(monkeypatch: pytest.MonkeyPatch, *keys: str) -> None:
    """Configure the given API keys for the duration of a test."""
    monkeypatch.setattr(settings, "api_keys", ",".join(keys))


async def upload(client: AsyncClient, key: str | None = None) -> Response:
    """POST an upload, optionally carrying an API key, and return the response."""
    headers = {"X-API-Key": key} if key is not None else {}
    return await client.post(
        "/api/v1/datasets",
        files={"file": ("test.csv", unique_sample_csv(), "text/csv")},
        headers=headers,
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


# ── Keys configured: writes require a valid key ───────────────────


@pytest.mark.asyncio
async def test_upload_rejects_missing_key(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    enable_auth(monkeypatch, API_KEY)

    response = await upload(client)

    assert response.status_code == 401
    assert "X-API-Key" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_rejects_wrong_key(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    enable_auth(monkeypatch, API_KEY)

    response = await upload(client, key="not-the-key")

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API key"


@pytest.mark.asyncio
async def test_upload_accepts_valid_key(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    enable_auth(monkeypatch, API_KEY)

    response = await upload(client, key=API_KEY)

    assert response.status_code == 201, response.text


@pytest.mark.asyncio
async def test_anchor_requires_key(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, mock_build_transaction
) -> None:
    enable_auth(monkeypatch, API_KEY)
    created = await upload(client, key=API_KEY)

    response = await client.post(
        f"/api/v1/datasets/{created.json()['dataset_id']}/anchor",
        json={"submitter_address": TEST_ADDRESS},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_submit_requires_key(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    enable_auth(monkeypatch, API_KEY)

    response = await client.post(
        "/api/v1/datasets/anything/submit",
        json={"signed_transaction_xdr": "AAAA..."},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_batch_create_requires_key(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    enable_auth(monkeypatch, API_KEY)

    response = await client.post(
        "/api/v1/batches",
        json={"submitter_address": TEST_ADDRESS, "dataset_ids": ["anything"]},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_batch_submit_requires_key(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    enable_auth(monkeypatch, API_KEY)

    response = await client.post(
        "/api/v1/batches/anything/submit",
        json={"signed_transaction_xdr": "AAAA..."},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_every_configured_key_is_accepted(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Whitespace around comma-separated keys is ignored on both sides."""
    enable_auth(monkeypatch, " alpha ", " beta ")

    first = await upload(client, key="alpha")
    second = await upload(client, key="beta")

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text


@pytest.mark.asyncio
async def test_reads_stay_public_when_auth_is_enabled(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    enable_auth(monkeypatch, API_KEY)

    response = await client.get("/api/v1/datasets")

    assert response.status_code == 200


# ── Public endpoints ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_stays_public_when_auth_is_enabled(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, mock_verify_on_chain_not_found
) -> None:
    """Permissionless verification is the point — it must not need a shared key."""
    enable_auth(monkeypatch, API_KEY)

    response = await client.post("/api/v1/verify", params={"dataset_hash": "a" * 64})

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_stays_public_when_auth_is_enabled(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    enable_auth(monkeypatch, API_KEY)

    with patch(
        "app.api.v1.health.check_rpc_connectivity",
        new=AsyncMock(return_value=True),
    ):
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# ── Key parsing ───────────────────────────────────────────────────


def test_configured_api_keys_trims_and_drops_blank_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "api_keys", " first , , second ,")

    assert configured_api_keys() == ["first", "second"]


def test_configured_api_keys_is_empty_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "api_keys", "")

    assert configured_api_keys() == []
