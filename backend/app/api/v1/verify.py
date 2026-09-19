"""Verification API endpoint: check dataset integrity proofs on-chain."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import MerkleError
from app.core.rate_limit import rate_limit
from app.core.uploads import read_upload
from app.db.session import get_db
from app.models.dataset import Dataset
from app.services import merkle
from app.services.ingest import process_upload
from app.services.parser import describe_supported_formats, is_supported
from app.services.soroban import verify_inclusion_on_chain, verify_on_chain

router = APIRouter(prefix="/verify")


async def _build_inclusion(dataset: Dataset) -> dict[str, Any] | None:
    """Describe how a dataset is proven inside its batch's Merkle root.

    Recomputes the proof locally and asks the contract to confirm the same
    proof, so a caller gets both a fast local answer and the on-chain verdict.
    Returns ``None`` for datasets anchored individually rather than in a batch.
    """
    if dataset.merkle_root is None or dataset.leaf_index is None or dataset.merkle_proof is None:
        return None

    try:
        verified_locally = merkle.verify_proof(
            dataset.dataset_hash,
            dataset.leaf_index,
            dataset.merkle_proof,
            dataset.merkle_root,
        )
    except MerkleError:
        verified_locally = False

    verified_on_chain = await verify_inclusion_on_chain(
        dataset.merkle_root,
        dataset.dataset_hash,
        dataset.leaf_index,
        dataset.merkle_proof,
    )

    return {
        "root": dataset.merkle_root,
        "leaf_index": dataset.leaf_index,
        "proof": dataset.merkle_proof,
        "batch_id": dataset.batch_id,
        "verified_locally": verified_locally,
        "verified_on_chain": verified_on_chain,
    }


@router.post("")
async def verify_dataset(
    dataset_hash: str | None = Query(None, description="SHA-256 hash of the dataset"),
    dataset_id: str | None = Query(None, description="Dataset UUID to verify"),
    file: UploadFile | None = None,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _rate_limit: None = Depends(rate_limit("verify")),  # noqa: B008
) -> dict[str, Any]:
    """Verify a dataset against its on-chain proof.

    Supports three modes:
    1. Provide a ``dataset_hash`` to directly query the contract.
    2. Provide a ``dataset_id`` to look up the hash from the database.
    3. Upload a CSV, JSON or XML file to re-compute the hash and verify.

    When the dataset was anchored as part of a Merkle batch, the response also
    carries an ``inclusion`` block with the proof needed to verify it against
    the anchored root.
    """
    resolved_hash: str | None = dataset_hash
    re_computed_hash: str | None = None
    local_record: dict[str, Any] | None = None
    local_dataset: Dataset | None = None

    # Mode 2: Look up dataset_id in the database
    if dataset_id and not resolved_hash and not file:
        result = await db.execute(select(Dataset).where(Dataset.dataset_id == dataset_id))
        ds = result.scalar_one_or_none()
        if ds:
            local_dataset = ds
            resolved_hash = ds.dataset_hash
            local_record = _local_record(ds)

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

    # Fall back to the stored dataset (by id, or by the resolved hash when the
    # caller supplied a hash or an upload) so batch membership is discoverable.
    if local_dataset is None and resolved_hash:
        result = await db.execute(select(Dataset).where(Dataset.dataset_hash == resolved_hash))
        local_dataset = result.scalar_one_or_none()

    if local_dataset is not None and local_record is None:
        local_record = _local_record(local_dataset)

    inclusion = await _build_inclusion(local_dataset) if local_dataset else None

    return {
        "match": on_chain is not None,
        "on_chain_record": on_chain,
        "local_record": local_record,
        "re_computed_hash": re_computed_hash,
        "inclusion": inclusion,
    }


def _local_record(dataset: Dataset) -> dict[str, Any]:
    """Summarise the stored dataset for the verification response."""
    return {
        "dataset_id": dataset.dataset_id,
        "anomaly_score": dataset.anomaly_score,
        "status": dataset.status,
        "created_at": dataset.created_at.isoformat() if dataset.created_at else None,
    }
