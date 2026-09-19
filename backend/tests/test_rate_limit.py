"""Tests for the in-process rate limiter on the upload and verify endpoints."""

import pytest
from httpx import AsyncClient

from app.config import settings
from tests.conftest import SAMPLE_HASH, unique_sample_csv


async def _upload(client: AsyncClient):
    """POST a unique upload so repeated calls do not collide on dataset_hash."""
    return await client.post(
        "/api/v1/datasets",
        files={"file": ("test.csv", unique_sample_csv(), "text/csv")},
    )


@pytest.mark.asyncio
async def test_upload_returns_429_after_the_limit_is_exceeded(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "rate_limit_requests", 2)

    first = await _upload(client)
    second = await _upload(client)
    third = await _upload(client)

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert third.status_code == 429
    assert third.headers["Retry-After"] == str(settings.rate_limit_window_seconds)
    assert "Rate limit exceeded" in third.json()["detail"]


@pytest.mark.asyncio
async def test_verify_returns_429_after_the_limit_is_exceeded(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    mock_verify_on_chain_not_found,
) -> None:
    monkeypatch.setattr(settings, "rate_limit_requests", 1)

    first = await client.post("/api/v1/verify", params={"dataset_hash": SAMPLE_HASH})
    second = await client.post("/api/v1/verify", params={"dataset_hash": SAMPLE_HASH})

    assert first.status_code == 200, first.text
    assert second.status_code == 429


@pytest.mark.asyncio
async def test_limit_is_tracked_per_endpoint(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    mock_verify_on_chain_not_found,
) -> None:
    """An upload does not consume the verification endpoint's allowance."""
    monkeypatch.setattr(settings, "rate_limit_requests", 1)

    upload = await _upload(client)
    verify = await client.post("/api/v1/verify", params={"dataset_hash": SAMPLE_HASH})

    assert upload.status_code == 201, upload.text
    assert verify.status_code == 200, verify.text


@pytest.mark.asyncio
async def test_rate_limiting_can_be_disabled(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    monkeypatch.setattr(settings, "rate_limit_requests", 1)

    for _ in range(3):
        response = await _upload(client)
        assert response.status_code == 201, response.text
