"""SQLAlchemy model for Merkle batch anchors.

A batch commits many dataset hashes to a single on-chain Merkle root, so the
storage cost of anchoring stays flat as the number of datasets grows.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Batch(Base):
    __tablename__ = "batches"

    batch_id: Mapped[str] = mapped_column(
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
    merkle_root: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
        comment="SHA-256 hex Merkle root committing to every dataset in the batch",
    )
    leaf_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Number of dataset leaves committed to by the root",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        comment="pending | anchored | failed",
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

    # TTL renewal bookkeeping
    root_ttl_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When the on-chain root entry expires unless renewed",
    )
    last_ttl_renewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last successful root TTL renewal",
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
        comment="Renewal attempts, so a root failing repeatedly is visible",
    )
    ttl_renewal_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Last renewal error, cleared on success",
    )
