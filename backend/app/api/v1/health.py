import asyncio
import logging

from fastapi import APIRouter
from stellar_sdk import SorobanServer

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


async def _check_soroban_rpc() -> str:
    """Attempt a lightweight Soroban RPC health check."""
    try:
        server = SorobanServer(settings.soroban_rpc_url)
        health = await asyncio.to_thread(server.get_health)
        if health.status == "healthy":
            return "connected"
        return f"unhealthy: {health}"
    except Exception as exc:
        logger.warning("Soroban RPC health check failed: %s", exc)
        return "unreachable"


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint. Verifies API and Soroban RPC connectivity."""
    soroban_status = await _check_soroban_rpc()
    overall = "ok" if soroban_status == "connected" else "degraded"
    return {
        "status": overall,
        "soroban_rpc": soroban_status,
    }
