"""SQLAlchemy model for geochemical dataset records."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Dataset(Base):
    __tablename__ = "datasets"

    dataset_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    submitter_address: Mapped[str] = mapped_column(
        String(56),
        nullable=False,
        index=True,
        comment="Stellar public key (G...) of the researcher",
    )
    dataset_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
        comment="SHA-256 hex digest of the canonicalized CSV",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        comment="pending | anchored | failed",
    )

    # Anomaly report
    anomaly_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        comment="Fraction of rows flagged as anomalous (0.0–1.0)",
    )
    anomaly_flags: Mapped[list[int] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="1-indexed row indices flagged as anomalous",
    )
    model_version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="AI model version tag (e.g., isoforest_v1)",
    )
    anomaly_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable anomaly summary string",
    )
    anomaly_warnings: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Geochemical plausibility findings raised at upload time",
    )

    # Merkle batch membership (populated when the dataset is anchored as part
    # of a batch rather than individually)
    batch_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
        comment="Batch this dataset was anchored in, if any",
    )
    merkle_root: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="Hex Merkle root of the batch containing this dataset",
    )
    leaf_index: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Position of this dataset's hash within the batch leaves",
    )
    merkle_proof: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Bottom-up hex sibling hashes proving batch inclusion",
    )

    # Transaction data
    unsigned_transaction_xdr: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Unsigned Soroban transaction XDR (base64)",
    )
    signed_transaction_xdr: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Researcher-signed transaction XDR (base64)",
    )
    stellar_tx_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="Stellar transaction hash after successful submission",
    )
    ledger_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Stellar ledger number where the transaction was confirmed",
    )
    explorer_url: Mapped[str | None] = mapped_column(
        String(256),
        nullable=True,
        comment="URL to view the transaction on Stellar Expert",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    anchored_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # TTL renewal bookkeeping for individually anchored datasets.
    #
    # A dataset anchored on its own gets a `Record(hash)` persistent entry, which
    # expires like any other. Batched datasets are covered by their batch root
    # instead, so only standalone ones carry a deadline here.
    ttl_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When the on-chain record expires unless renewed",
    )
    last_ttl_renewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last successful record TTL renewal",
    )
    ttl_renewal_tx_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="Transaction hash of the most recent successful renewal",
    )
    ttl_renewal_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Renewal attempts, so a record failing repeatedly is visible",
    )
    ttl_renewal_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Last renewal error, cleared on success",
    )
