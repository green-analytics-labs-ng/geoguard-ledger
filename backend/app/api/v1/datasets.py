"""Dataset API endpoints with PostgreSQL persistence."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.uploads import read_upload
from app.db.session import get_db
from app.models.dataset import Dataset
from app.services.anomaly import run_anomaly_detection
from app.services.hasher import CANONICALIZATION_VERSION
from app.services.ingest import process_upload
from app.services.parser import describe_supported_formats, is_supported
from app.services.soroban import build_anchor_transaction, submit_transaction
from app.services.ttl_renewal import initial_ttl_expiry

router = APIRouter(prefix="/datasets")


class AnomalyReport(BaseModel):
    score: float
    flags: list[int]
    model_version: str
    summary: str
    warnings: list[str] = Field(default_factory=list)


class DatasetAnalyzeResponse(BaseModel):
    """Result of canonicalizing, hashing, and analyzing one upload.

    Carries no transaction on purpose: analysis needs no wallet, so the
    unsigned anchor transaction is not built until the researcher supplies an
    address at ``POST /datasets/{id}/anchor``.
    """

    dataset_id: str
    dataset_hash: str
    canonicalization_version: str
    anomaly_report: AnomalyReport
    created_at: str


class AnchorRequest(BaseModel):
    submitter_address: str = Field(
        ...,
        description="Stellar public key of the researcher who will sign the anchor",
    )


class DatasetAnchorResponse(BaseModel):
    dataset_id: str
    dataset_hash: str
    unsigned_transaction_xdr: str


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
    canonicalization_version: str
    status: str
    anomaly_score: float
    anomaly_report: AnomalyReport | None = None
    stellar_tx_hash: str | None = None
    explorer_url: str | None = None
    batch_id: str | None = None
    merkle_root: str | None = None
    leaf_index: int | None = None
    merkle_proof: list[str] | None = None
    created_at: str
    anchored_at: str | None = None


class DatasetListResponse(BaseModel):
    datasets: list[DatasetResponse]
    total: int


@router.post(
    "",
    response_model=DatasetAnalyzeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def analyze_dataset(
    file: UploadFile = File(...),  # noqa: B008
    submitter_address: str | None = Form(None),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> Any:
    """Canonicalize, hash, and analyze an uploaded dataset. No wallet required.

    Nothing is committed to the network here, so there is nothing to sign yet:
    the dataset is stored as ``analyzed`` with no submitter, and the address is
    bound later by ``POST /datasets/{id}/anchor``. Splitting the two is what
    lets a researcher see the hash and the anomaly report before deciding to
    connect a wallet at all.
    """
    # Rejected rather than ignored. A caller still sending the address is using
    # the old contract: it would get a 201 with no transaction in the body and
    # fail much later, at the signing step, with no hint as to why.
    if submitter_address is not None:
        raise HTTPException(
            status_code=400,
            detail=(
                "submitter_address is not accepted here anymore — analyze the file "
                "first, then POST /datasets/{dataset_id}/anchor with the address."
            ),
        )

    # Validate file format (CSV, JSON or XML)
    if not file.filename or not is_supported(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"File must be one of: {describe_supported_formats()}",
        )

    content = await read_upload(file)
    processed = process_upload(content, file.filename)

    # SHA-256 over the canonicalized upload
    dataset_hash = processed.dataset_hash

    # Run AI anomaly detection on the same canonical representation
    anomaly_result = run_anomaly_detection(processed.analysis_text, processed.file_format)

    # Persist to database
    dataset = Dataset(
        submitter_address=None,
        dataset_hash=dataset_hash,
        status="analyzed",
        anomaly_score=anomaly_result["score"],
        anomaly_flags=anomaly_result["flags"],
        model_version=anomaly_result["model_version"],
        anomaly_summary=anomaly_result["summary"],
        anomaly_warnings=anomaly_result.get("warnings", []),
    )
    db.add(dataset)
    await db.commit()
    await db.refresh(dataset)

    return DatasetAnalyzeResponse(
        dataset_id=dataset.dataset_id,
        dataset_hash=dataset.dataset_hash,
        canonicalization_version=CANONICALIZATION_VERSION,
        anomaly_report=AnomalyReport(
            score=anomaly_result["score"],
            flags=anomaly_result["flags"],
            model_version=anomaly_result["model_version"],
            summary=anomaly_result["summary"],
            warnings=anomaly_result.get("warnings", []),
        ),
        created_at=dataset.created_at.isoformat()
        if dataset.created_at
        else datetime.now(UTC).isoformat(),
    )


@router.post("/{dataset_id}/anchor", response_model=DatasetAnchorResponse)
async def anchor_dataset(
    dataset_id: str,
    body: AnchorRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> Any:
    """Build the unsigned anchoring transaction for an analyzed dataset.

    This is the wallet step. The address becomes the transaction's source
    account and the dataset's submitter, so whoever signs is the one the ledger
    records as having anchored it — and the one a batch has to agree with.
    """
    if not body.submitter_address.startswith("G"):
        raise HTTPException(
            status_code=400,
            detail="Invalid Stellar public key — must start with 'G'",
        )

    result = await db.execute(select(Dataset).where(Dataset.dataset_id == dataset_id))
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    if dataset.status == "anchored":
        raise HTTPException(status_code=409, detail="Dataset is already anchored")

    # A dataset already bound to an address can only be re-anchored by that
    # same owner. Still `analyzed` or `pending` means the transaction was never
    # submitted, so rebuilding it is a retry rather than a takeover.
    if dataset.submitter_address not in (None, body.submitter_address):
        raise HTTPException(
            status_code=403,
            detail="Dataset belongs to a different submitter",
        )

    # Rebuild the anomaly report from the stored columns: the on-chain call
    # carries the score and model version that this dataset was analyzed with.
    anomaly_report = {
        "score": dataset.anomaly_score,
        "model_version": dataset.model_version or "",
        "flags": dataset.anomaly_flags or [],
        "summary": dataset.anomaly_summary or "",
    }

    xdr = await build_anchor_transaction(
        body.submitter_address,
        dataset.dataset_hash,
        anomaly_report,
    )

    dataset.submitter_address = body.submitter_address
    dataset.unsigned_transaction_xdr = xdr
    dataset.status = "pending"
    await db.commit()

    return DatasetAnchorResponse(
        dataset_id=dataset.dataset_id,
        dataset_hash=dataset.dataset_hash,
        unsigned_transaction_xdr=xdr,
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
        # anchor_hash pushes the new record's TTL out to its full budget on
        # write, so record the deadline the renewal job has to beat. Without it
        # this dataset would never be selected and its record would be archived
        # at the network's minimum persistent-entry TTL.
        dataset.ttl_expires_at = initial_ttl_expiry(dataset.anchored_at)
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
            warnings=dataset.anomaly_warnings or [],
        )

    return DatasetResponse(
        dataset_id=dataset.dataset_id,
        dataset_hash=dataset.dataset_hash,
        canonicalization_version=CANONICALIZATION_VERSION,
        status=dataset.status,
        anomaly_score=dataset.anomaly_score,
        anomaly_report=anomaly_report,
        stellar_tx_hash=dataset.stellar_tx_hash,
        explorer_url=dataset.explorer_url,
        batch_id=dataset.batch_id,
        merkle_root=dataset.merkle_root,
        leaf_index=dataset.leaf_index,
        merkle_proof=dataset.merkle_proof,
        created_at=dataset.created_at.isoformat() if dataset.created_at else "",
        anchored_at=dataset.anchored_at.isoformat() if dataset.anchored_at else None,
    )
