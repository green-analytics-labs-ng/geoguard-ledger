from fastapi import APIRouter

from app.config import settings
from app.services.soroban import check_rpc_connectivity

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint.

    Probes the Soroban RPC endpoint on every call so monitoring and alerting
    see the real status of the dependency the API relies on, rather than an
    unconditional "connected".

    Also reports the network passphrase transactions are built and verified
    against. The frontend needs it to notice that a connected wallet is signing
    for a different network than this deployment anchors to — a mismatch that
    produces a signature the contract rejects, with nothing in the error to say
    why. It is reported from here rather than configured in the frontend because
    the transaction is built server-side: the backend's passphrase is the only
    thing that decides which signature will be accepted, so a second copy could
    only ever disagree with it.
    """
    rpc_connected = await check_rpc_connectivity()

    return {
        "status": "ok",
        "soroban_rpc": "connected" if rpc_connected else "unreachable",
        "network_passphrase": settings.soroban_network_passphrase,
    }
