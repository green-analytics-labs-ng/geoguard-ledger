"""Batch anchoring API: commit many dataset hashes under one Merkle root.

Individual anchoring costs one Persistent ledger entry (and one rent
obligation) per dataset. A batch collapses that to a single root, which is what
lets the system keep anchoring datasets as submission volume grows.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import MerkleError
from app.db.session import get_db
from app.models.batch import Batch
from app.models.dataset import Dataset
from app.services import merkle
from app.services.soroban import build_anchor_root_transaction, submit_transaction
from app.services.ttl_renewal import initial_ttl_expiry

router = APIRouter(prefix="/batches")


class BatchCreateRequest(BaseModel):
    submitter_address: str = Field(..., description="Stellar public key of the researcher")
    dataset_ids: list[str] = Field(
        ...,
        min_length=1,
        description="Dataset IDs to include, in the order they become Merkle leaves",
    )


class BatchLeaf(BaseModel):
    dataset_id: str
    dataset_hash: str
    leaf_index: int
    merkle_proof: list[str]
    anomaly_score: float


class BatchCreateResponse(BaseModel):
    batch_id: str
    merkle_root: str
    leaf_count: int
    unsigned_transaction_xdr: str
    leaves: list[BatchLeaf]
    created_at: str


class BatchSubmitRequest(BaseModel):
    signed_transaction_xdr: str


class BatchSubmitResponse(BaseModel):
    batch_id: str
    status: str
    stellar_tx_hash: str
    ledger_number: int
    explorer_url: str
    anchored_at: str


class BatchResponse(BaseModel):
    batch_id: str
    merkle_root: str
    leaf_count: int
    submitter_address: str
    status: str
    stellar_tx_hash: str | None = None
    explorer_url: str | None = None
    created_at: str
    anchored_at: str | None = None


class BatchListResponse(BaseModel):
    batches: list[BatchResponse]
    total: int


def _explorer_url(tx_hash: str) -> str:
    return f"https://stellar.expert/explorer/testnet/tx/{tx_hash}"


def _batch_to_response(batch: Batch) -> BatchResponse:
    return BatchResponse(
        batch_id=batch.batch_id,
        merkle_root=batch.merkle_root,
        leaf_count=batch.leaf_count,
        submitter_address=batch.submitter_address,
        status=batch.status,
        stellar_tx_hash=batch.stellar_tx_hash,
        explorer_url=batch.explorer_url,
        created_at=batch.created_at.isoformat() if batch.created_at else "",
        anchored_at=batch.anchored_at.isoformat() if batch.anchored_at else None,
    )


@router.post("", response_model=BatchCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_batch(
    body: BatchCreateRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> Any:
    """Build a Merkle root over the given datasets and return an unsigned anchor transaction.

    Leaves are committed in the order of ``dataset_ids``, and that order defines
    each dataset's ``leaf_index``. The returned proofs are stored with each
    dataset, so verification does not depend on reconstructing the batch later.
    """
    if not body.submitter_address.startswith("G"):
        raise HTTPException(
            status_code=400,
            detail="Invalid Stellar public key — must start with 'G'",
        )

    dataset_ids = body.dataset_ids
    if len(dataset_ids) != len(set(dataset_ids)):
        raise HTTPException(status_code=400, detail="dataset_ids must not contain duplicates")
    if len(dataset_ids) > settings.max_batch_size:
        raise HTTPException(
            status_code=400,
            detail=f"A batch may contain at most {settings.max_batch_size} datasets",
        )

    # Load the datasets, then re-order them to match the requested leaf order.
    result = await db.execute(select(Dataset).where(Dataset.dataset_id.in_(dataset_ids)))
    datasets_by_id = {ds.dataset_id: ds for ds in result.scalars().all()}

    missing = [dataset_id for dataset_id in dataset_ids if dataset_id not in datasets_by_id]
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown dataset ids: {', '.join(missing)}",
        )

    datasets = [datasets_by_id[dataset_id] for dataset_id in dataset_ids]

    not_owned = [ds.dataset_id for ds in datasets if ds.submitter_address != body.submitter_address]
    if not_owned:
        raise HTTPException(
            status_code=403,
            detail="All datasets in a batch must belong to the submitting address",
        )

    already_batched = [ds.dataset_id for ds in datasets if ds.batch_id is not None]
    if already_batched:
        raise HTTPException(
            status_code=409,
            detail=f"Datasets already anchored in a batch: {', '.join(already_batched)}",
        )

    hashes = [ds.dataset_hash for ds in datasets]

    try:
        merkle_root = merkle.compute_root(hashes)
    except MerkleError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc

    # Build the unsigned anchoring transaction before persisting anything, so a
    # failure here leaves no half-written batch behind.
    xdr = await build_anchor_root_transaction(body.submitter_address, merkle_root, len(hashes))

    batch = Batch(
        submitter_address=body.submitter_address,
        merkle_root=merkle_root,
        leaf_count=len(hashes),
        status="pending",
        unsigned_transaction_xdr=xdr,
    )
    db.add(batch)
    await db.flush()

    leaves: list[BatchLeaf] = []
    for index, dataset in enumerate(datasets):
        proof = merkle.generate_proof(hashes, index)
        dataset.batch_id = batch.batch_id
        dataset.merkle_root = merkle_root
        dataset.leaf_index = index
        dataset.merkle_proof = proof
        leaves.append(
            BatchLeaf(
                dataset_id=dataset.dataset_id,
                dataset_hash=dataset.dataset_hash,
                leaf_index=index,
                merkle_proof=proof,
                anomaly_score=dataset.anomaly_score,
            )
        )

    await db.commit()
    await db.refresh(batch)

    return BatchCreateResponse(
        batch_id=batch.batch_id,
        merkle_root=merkle_root,
        leaf_count=batch.leaf_count,
        unsigned_transaction_xdr=xdr,
        leaves=leaves,
        created_at=batch.created_at.isoformat()
        if batch.created_at
        else datetime.now(UTC).isoformat(),
    )


@router.post("/{batch_id}/submit", response_model=BatchSubmitResponse)
async def submit_batch(
    batch_id: str,
    body: BatchSubmitRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> Any:
    """Submit a researcher-signed root transaction and mark the batch anchored."""
    result = await db.execute(select(Batch).where(Batch.batch_id == batch_id))
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    if batch.status == "anchored":
        raise HTTPException(status_code=409, detail="Batch is already anchored")

    batch.signed_transaction_xdr = body.signed_transaction_xdr

    try:
        tx_result = await submit_transaction(body.signed_transaction_xdr)
    except Exception as exc:
        batch.status = "failed"
        await db.commit()
        raise HTTPException(
            status_code=502,
            detail=f"Transaction submission failed: {exc}",
        ) from exc

    anchored_at = datetime.now(UTC)
    batch.status = "anchored"
    batch.stellar_tx_hash = tx_result["tx_hash"]
    batch.ledger_number = tx_result["ledger"]
    batch.explorer_url = _explorer_url(tx_result["tx_hash"])
    batch.anchored_at = anchored_at
    # The contract pushes a new root's TTL out to its full budget when it is
    # written, so record the deadline the renewal job has to beat.
    batch.root_ttl_expires_at = initial_ttl_expiry(anchored_at)

    # Every dataset covered by the root is now provably anchored.
    members = await db.execute(select(Dataset).where(Dataset.batch_id == batch.batch_id))
    for dataset in members.scalars().all():
        dataset.status = "anchored"
        dataset.stellar_tx_hash = tx_result["tx_hash"]
        dataset.ledger_number = tx_result["ledger"]
        dataset.explorer_url = batch.explorer_url
        dataset.anchored_at = anchored_at

    await db.commit()

    return BatchSubmitResponse(
        batch_id=batch.batch_id,
        status=batch.status,
        stellar_tx_hash=batch.stellar_tx_hash or "",
        ledger_number=batch.ledger_number or 0,
        explorer_url=batch.explorer_url or "",
        anchored_at=batch.anchored_at.isoformat() if batch.anchored_at else "",
    )


@router.get("", response_model=BatchListResponse)
async def list_batches(
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> Any:
    """List batches, most recent first."""
    result = await db.execute(select(Batch).order_by(Batch.created_at.desc()))
    batches = result.scalars().all()
    return BatchListResponse(
        batches=[_batch_to_response(batch) for batch in batches],
        total=len(batches),
    )


@router.get("/{batch_id}", response_model=BatchResponse)
async def get_batch(
    batch_id: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> Any:
    """Get a single batch by ID."""
    result = await db.execute(select(Batch).where(Batch.batch_id == batch_id))
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    return _batch_to_response(batch)
