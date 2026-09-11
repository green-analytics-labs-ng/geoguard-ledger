"""Verification API endpoint: check dataset integrity proofs on-chain."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.uploads import read_upload
from app.db.session import get_db
from app.models.dataset import Dataset
from app.services.ingest import process_upload
from app.services.parser import describe_supported_formats, is_supported
from app.services.soroban import verify_on_chain

router = APIRouter(prefix="/verify")


@router.post("")
async def verify_dataset(
    dataset_hash: str | None = Query(None, description="SHA-256 hash of the dataset"),
    dataset_id: str | None = Query(None, description="Dataset UUID to verify"),
    file: UploadFile | None = None,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict[str, Any]:
    """Verify a dataset against its on-chain proof.

    Supports three modes:
    1. Provide a ``dataset_hash`` to directly query the contract.
    2. Provide a ``dataset_id`` to look up the hash from the database.
    3. Upload a CSV, JSON or XML file to re-compute the hash and verify.
    """
    resolved_hash: str | None = dataset_hash
    re_computed_hash: str | None = None
    local_record: dict[str, Any] | None = None

    # Mode 2: Look up dataset_id in the database
    if dataset_id and not resolved_hash and not file:
        result = await db.execute(select(Dataset).where(Dataset.dataset_id == dataset_id))
        ds = result.scalar_one_or_none()
        if ds:
            resolved_hash = ds.dataset_hash
            local_record = {
                "dataset_id": ds.dataset_id,
                "anomaly_score": ds.anomaly_score,
                "status": ds.status,
                "created_at": ds.created_at.isoformat() if ds.created_at else None,
            }

    # Mode 3: If a file was provided, re-compute its hash and verify
    if file:
        if not file.filename or not is_supported(file.filename):
            raise HTTPException(
                status_code=400,
                detail=f"File must be one of: {describe_supported_formats()}",
            )
        content = await read_upload(file)
        re_computed_hash = process_upload(content, file.filename).dataset_hash
        resolved_hash = re_computed_hash

    # Query the contract
    on_chain: dict[str, Any] | None = None
    if resolved_hash:
        on_chain = await verify_on_chain(resolved_hash)

    # If not found on-chain but we have a local record, try to reconcile
    if not on_chain and dataset_id and not local_record:
        result = await db.execute(select(Dataset).where(Dataset.dataset_id == dataset_id))
        ds = result.scalar_one_or_none()
        if ds:
            local_record = {
                "dataset_id": ds.dataset_id,
                "anomaly_score": ds.anomaly_score,
                "status": ds.status,
                "created_at": ds.created_at.isoformat() if ds.created_at else None,
            }

    return {
        "match": on_chain is not None,
        "on_chain_record": on_chain,
        "local_record": local_record,
        "re_computed_hash": re_computed_hash,
    }
