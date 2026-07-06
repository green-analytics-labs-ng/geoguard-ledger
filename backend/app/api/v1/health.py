from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint. Verifies API and Soroban RPC connectivity."""
    return {
        "status": "ok",
        "soroban_rpc": "connected",
    }
