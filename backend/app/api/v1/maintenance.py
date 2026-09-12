"""Maintenance endpoints: operational status that callers do not query for data.

Kept separate from ``/health`` so monitoring that just wants a liveness signal
does not pay for a database aggregate on every probe.
"""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.ttl_renewal import get_ttl_status

router = APIRouter(prefix="/maintenance")


@router.get("/ttl-status")
async def ttl_status(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:  # noqa: B008
    """Report how much life the anchored Merkle roots have left.

    A root that is archived makes every dataset in its batch unverifiable, so
    the counts here — roots due for renewal, already past their recorded expiry,
    and failing to renew — are the signal that the ledger's central promise is
    still being kept. ``roots_past_recorded_expiry`` above zero means the
    renewal job is not running or is unable to keep up.
    """
    return await get_ttl_status(db)
