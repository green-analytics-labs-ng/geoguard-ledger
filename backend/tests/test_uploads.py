"""Tests for server-side upload size enforcement.

The frontend enforces a 50 MB limit, but that is trivially bypassed by calling
the API directly, so the backend rejects oversized uploads itself.
"""

import io

import pytest
from fastapi import HTTPException, UploadFile
from httpx import AsyncClient

from app.config import settings
from app.core.uploads import read_upload

TEST_ADDRESS = "GABCDEF123456789012345678901234567890123"

# Small but structurally valid CSV, used to prove the limit does not reject
# uploads that are within bounds.
SMALL_CSV = (
    "sample_id,latitude,longitude,pH,conductivity,dissolved_oxygen,temperature\n"
    "S001,34.052200,-118.243700,7.20,450.00,8.50,22.10\n"
    "S002,34.052500,-118.244000,7.15,452.00,8.30,22.30\n"
    "S003,34.052800,-118.244300,7.18,448.00,8.70,22.00\n"
    "S004,34.053100,-118.244600,7.22,455.00,8.40,22.20\n"
    "S005,34.053400,-118.244900,7.19,449.00,8.60,22.40\n"
)

# A payload comfortably larger than the limit used in the tests below.
LIMIT = 1024
OVERSIZED_CSV = "sample_id,pH,conductivity\n" + "S001,7.20,450.00\n" * 200


def _use_small_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "max_upload_size_bytes", LIMIT)


# ── read_upload helper ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_read_upload_accepts_file_within_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_small_limit(monkeypatch)
    upload = UploadFile(file=io.BytesIO(b"a,b\n1,2\n"), size=8, filename="small.csv")
    assert await read_upload(upload) == b"a,b\n1,2\n"


@pytest.mark.asyncio
async def test_read_upload_rejects_oversized_declared_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_small_limit(monkeypatch)
    upload = UploadFile(file=io.BytesIO(b"x"), size=LIMIT + 1, filename="big.csv")

    with pytest.raises(HTTPException) as excinfo:
        await read_upload(upload)

    assert excinfo.value.status_code == 413


@pytest.mark.asyncio
async def test_read_upload_checks_body_when_size_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Defence in depth: clients that omit their size are still bounded."""
    _use_small_limit(monkeypatch)
    upload = UploadFile(file=io.BytesIO(b"x" * (LIMIT + 1)), size=None, filename="big.csv")

    with pytest.raises(HTTPException) as excinfo:
        await read_upload(upload)

    assert excinfo.value.status_code == 413


# ── POST /api/v1/datasets ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_dataset_rejects_oversized_upload(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_small_limit(monkeypatch)

    response = await client.post(
        "/api/v1/datasets",
        data={"submitter_address": TEST_ADDRESS},
        files={"file": ("big.csv", OVERSIZED_CSV, "text/csv")},
    )

    assert response.status_code == 413
    assert "maximum upload size" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_dataset_accepts_upload_within_limit(
    client: AsyncClient,
    mock_build_transaction,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_small_limit(monkeypatch)

    response = await client.post(
        "/api/v1/datasets",
        data={"submitter_address": TEST_ADDRESS},
        files={"file": ("small.csv", SMALL_CSV, "text/csv")},
    )

    assert response.status_code == 201


# ── POST /api/v1/verify ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_rejects_oversized_upload(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_small_limit(monkeypatch)

    response = await client.post(
        "/api/v1/verify",
        files={"file": ("big.csv", OVERSIZED_CSV, "text/csv")},
    )

    assert response.status_code == 413


@pytest.mark.asyncio
async def test_verify_accepts_upload_within_limit(
    client: AsyncClient,
    mock_verify_on_chain_not_found,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_small_limit(monkeypatch)

    response = await client.post(
        "/api/v1/verify",
        files={"file": ("small.csv", SMALL_CSV, "text/csv")},
    )

    assert response.status_code == 200
    assert len(response.json()["re_computed_hash"]) == 64
