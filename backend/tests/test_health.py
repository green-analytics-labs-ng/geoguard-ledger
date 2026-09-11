"""Tests for real Soroban RPC connectivity reporting on GET /health.

The endpoint previously returned a hardcoded ``"connected"``, which produced
false positives in monitoring whenever the RPC node was down.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.services.soroban import check_rpc_connectivity

TEST_ADDRESS = "GABCDEF123456789012345678901234567890123"


# ── check_rpc_connectivity ────────────────────────────────────────


@pytest.mark.asyncio
async def test_probe_returns_true_for_healthy_node(monkeypatch: pytest.MonkeyPatch) -> None:
    server = SimpleNamespace(get_health=lambda: SimpleNamespace(status="healthy"))
    monkeypatch.setattr("app.services.soroban._get_server", lambda: server)

    assert await check_rpc_connectivity() is True


@pytest.mark.asyncio
async def test_probe_returns_false_for_unhealthy_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SimpleNamespace(get_health=lambda: SimpleNamespace(status="unhealthy"))
    monkeypatch.setattr("app.services.soroban._get_server", lambda: server)

    assert await check_rpc_connectivity() is False


@pytest.mark.asyncio
async def test_probe_returns_false_when_rpc_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> None:
        raise ConnectionError("connection refused")

    server = SimpleNamespace(get_health=boom)
    monkeypatch.setattr("app.services.soroban._get_server", lambda: server)

    assert await check_rpc_connectivity() is False


@pytest.mark.asyncio
async def test_probe_returns_false_when_rpc_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    import time

    def slow() -> None:
        time.sleep(0.3)
        return None

    server = SimpleNamespace(get_health=slow)
    monkeypatch.setattr("app.services.soroban._get_server", lambda: server)
    monkeypatch.setattr("app.services.soroban.settings.soroban_rpc_health_timeout_seconds", 0.05)

    assert await check_rpc_connectivity() is False


# ── GET /api/v1/health ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_health_reports_connected_when_probe_succeeds(client: AsyncClient) -> None:
    with patch(
        "app.api.v1.health.check_rpc_connectivity",
        new=AsyncMock(return_value=True),
    ):
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "soroban_rpc": "connected"}


@pytest.mark.asyncio
async def test_health_reports_unreachable_when_probe_fails(client: AsyncClient) -> None:
    with patch(
        "app.api.v1.health.check_rpc_connectivity",
        new=AsyncMock(return_value=False),
    ):
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["soroban_rpc"] == "unreachable"
