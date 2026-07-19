"""Dataset API endpoints with PostgreSQL persistence."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.models.dataset import Dataset
from app.services.anomaly import run_anomaly_detection
from app.services.hasher import compute_hash
from app.services.parser import is_supported, parse_to_csv
from app.services.soroban import build_anchor_transaction, submit_transaction

router = APIRouter(prefix="/datasets")


class AnomalyReport(BaseModel):
    score: float
    flags: list[int]
    model_version: str
    summary: str


class DatasetCreateResponse(BaseModel):
    dataset_id: str
    dataset_hash: str
    anomaly_report: AnomalyReport
    unsigned_transaction_xdr: str
    created_at: str


class SubmitRequest(BaseModel):
    signed_transaction_xdr: str


class SubmitResponse(BaseModel):
    dataset_id: str
    status: str
    stellar_tx_hash: str
    ledger_number: int
    explorer_url: str
    anchored_at: str


class DatasetResponse(BaseModel):
    dataset_id: str
    dataset_hash: str
    status: str
    anomaly_score: float
    anomaly_report: AnomalyReport | None = None
    stellar_tx_hash: str | None = None
    explorer_url: str | None = None
    created_at: str
    anchored_at: str | None = None


class DatasetListResponse(BaseModel):
    datasets: list[DatasetResponse]
    total: int


@router.post(
    "",
    response_model=DatasetCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_dataset(
    submitter_address: str = Form(  # noqa: B008
        ...,
        description="Stellar public key of the researcher",
    ),
    file: UploadFile = File(...),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> Any:
    """Upload and process a new geochemical dataset."""
    # Validate submitter address
    if not submitter_address.startswith("G"):
        raise HTTPException(
            status_code=400,
            detail="Invalid Stellar public key — must start with 'G'",
        )

    # Validate file format (CSV or JSON)
    if not file.filename or not is_supported(file.filename):
        raise HTTPException(
            status_code=400,
            detail="File must be a .csv or .json file",
        )

    if file.size is not None and file.size > settings.max_upload_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large — maximum size is {settings.max_upload_size // (1024 * 1024)} MB",
        )

    content = await file.read()
    csv_text = parse_to_csv(content, file.filename)

    # Compute SHA-256 hash
    dataset_hash = compute_hash(csv_text)

    # Run AI anomaly detection
    anomaly_result = run_anomaly_detection(csv_text)

    # Build unsigned Soroban transaction
    xdr = await build_anchor_transaction(submitter_address, dataset_hash, anomaly_result)

    # Persist to database
    dataset = Dataset(
        submitter_address=submitter_address,
        dataset_hash=dataset_hash,
        status="pending",
        anomaly_score=anomaly_result["score"],
        anomaly_flags=anomaly_result["flags"],
        model_version=anomaly_result["model_version"],
        anomaly_summary=anomaly_result["summary"],
        unsigned_transaction_xdr=xdr,
    )
    db.add(dataset)
    await db.commit()
    await db.refresh(dataset)

    return DatasetCreateResponse(
        dataset_id=dataset.dataset_id,
        dataset_hash=dataset.dataset_hash,
        anomaly_report=AnomalyReport(
            score=anomaly_result["score"],
            flags=anomaly_result["flags"],
            model_version=anomaly_result["model_version"],
            summary=anomaly_result["summary"],
        ),
        unsigned_transaction_xdr=xdr,
        created_at=dataset.created_at.isoformat()
        if dataset.created_at
        else datetime.now(UTC).isoformat(),
    )


@router.post("/{dataset_id}/submit", response_model=SubmitResponse)
async def submit_dataset(
    dataset_id: str,
    body: SubmitRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> Any:
    """Submit a researcher-signed transaction to the Stellar network."""
    # Load the dataset from DB
    result = await db.execute(select(Dataset).where(Dataset.dataset_id == dataset_id))
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Persist the signed XDR
    dataset.signed_transaction_xdr = body.signed_transaction_xdr

    # Submit the signed transaction to Soroban RPC
    try:
        tx_result = await submit_transaction(body.signed_transaction_xdr)
        dataset.status = "anchored"
        dataset.stellar_tx_hash = tx_result["tx_hash"]
        dataset.ledger_number = tx_result["ledger"]
        dataset.explorer_url = f"https://stellar.expert/explorer/testnet/tx/{tx_result['tx_hash']}"
        dataset.anchored_at = datetime.now(UTC)
    except Exception as exc:
        dataset.status = "failed"
        await db.commit()
        raise HTTPException(
            status_code=502,
            detail=f"Transaction submission failed: {exc}",
        ) from exc

    await db.commit()

    return SubmitResponse(
        dataset_id=dataset.dataset_id,
        status=dataset.status,
        stellar_tx_hash=dataset.stellar_tx_hash or "",
        ledger_number=dataset.ledger_number or 0,
        explorer_url=dataset.explorer_url or "",
        anchored_at=dataset.anchored_at.isoformat() if dataset.anchored_at else "",
    )


@router.get("", response_model=DatasetListResponse)
async def list_datasets(
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> Any:
    """List all datasets, ordered by most recent first."""
    result = await db.execute(select(Dataset).order_by(Dataset.created_at.desc()))
    datasets = result.scalars().all()
    return DatasetListResponse(
        datasets=[_dataset_to_response(ds) for ds in datasets],
        total=len(datasets),
    )


@router.get("/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> Any:
    """Get full details for a single dataset."""
    result = await db.execute(select(Dataset).where(Dataset.dataset_id == dataset_id))
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return _dataset_to_response(dataset)


def _dataset_to_response(dataset: Dataset) -> DatasetResponse:
    """Convert a Dataset ORM object to a DatasetResponse."""
    anomaly_report: AnomalyReport | None = None
    if dataset.model_version:
        anomaly_report = AnomalyReport(
            score=dataset.anomaly_score,
            flags=dataset.anomaly_flags or [],
            model_version=dataset.model_version,
            summary=dataset.anomaly_summary or "",
        )

    return DatasetResponse(
        dataset_id=dataset.dataset_id,
        dataset_hash=dataset.dataset_hash,
        status=dataset.status,
        anomaly_score=dataset.anomaly_score,
        anomaly_report=anomaly_report,
        stellar_tx_hash=dataset.stellar_tx_hash,
        explorer_url=dataset.explorer_url,
        created_at=dataset.created_at.isoformat() if dataset.created_at else "",
        anchored_at=dataset.anchored_at.isoformat() if dataset.anchored_at else None,
    )
