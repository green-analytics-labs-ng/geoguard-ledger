from fastapi import APIRouter

from app.services.soroban import check_rpc_connectivity

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint.

    Probes the Soroban RPC endpoint on every call so monitoring and alerting
    see the real status of the dependency the API relies on, rather than an
    unconditional "connected".
    """
    rpc_connected = await check_rpc_connectivity()

    return {
        "status": "ok",
        "soroban_rpc": "connected" if rpc_connected else "unreachable",
    }
