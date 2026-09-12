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
    """Report how much life the anchored entries have left, by kind.

    An archived entry stops answering verification, taking its datasets with it —
    a batch root covers every dataset in the batch, a record covers one dataset
    anchored on its own. The counts here (due for renewal, already past their
    recorded expiry, failing to renew) are the signal that the ledger's central
    promise is still being kept. A ``past_recorded_expiry`` above zero under
    either kind means the renewal job is not running or cannot keep up.
    """
    return await get_ttl_status(db)
