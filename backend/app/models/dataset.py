"""SQLAlchemy model for geochemical dataset records."""

import uuid
from datetime import UTC, datetime
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
        comment="AI model version tag (e.g., isoforest-v1)",
    )
    anomaly_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable anomaly summary string",
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
