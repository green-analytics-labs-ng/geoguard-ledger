"""add dataset ttl renewal tracking

Adds the bookkeeping the TTL renewal job needs for individually anchored
datasets: when a dataset's own anchor record expires, what the last renewal did,
and whether it is failing repeatedly.

Batched datasets are deliberately left NULL. They are covered by their batch
root rather than by a record of their own, so giving them a deadline would make
the job call `extend_ttl` for a record that does not exist.

Existing standalone anchors are backfilled so they are eligible for renewal.
Without that they would have a NULL deadline, never be selected, and expire
silently — the very failure this migration exists to prevent.

Revision ID: 849a9e96fe36
Revises: feab874bc90d
Create Date: 2026-09-12 11:45:00.000000

"""

from collections.abc import Sequence
from datetime import timedelta

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "849a9e96fe36"
down_revision: str | Sequence[str] | None = "feab874bc90d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Mirrors RECORD_TTL_EXTEND_TO in contracts/geoguard-ledger/src/storage.rs
# (3,110,400 ledgers at ~5s each). Frozen here on purpose: a migration must not
# follow a constant that can change later.
ANCHORED_RECORD_LIFETIME = timedelta(days=180)


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "datasets",
        sa.Column(
            "ttl_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When the on-chain record expires unless renewed",
        ),
    )
    op.add_column(
        "datasets",
        sa.Column(
            "last_ttl_renewed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last successful record TTL renewal",
        ),
    )
    op.add_column(
        "datasets",
        sa.Column(
            "ttl_renewal_tx_hash",
            sa.String(length=64),
            nullable=True,
            comment="Transaction hash of the most recent successful renewal",
        ),
    )
    op.add_column(
        "datasets",
        sa.Column(
            "ttl_renewal_attempts",
            sa.Integer(),
            server_default="0",
            nullable=False,
            comment="Renewal attempts, so a record failing repeatedly is visible",
        ),
    )
    op.add_column(
        "datasets",
        sa.Column(
            "ttl_renewal_error",
            sa.Text(),
            nullable=True,
            comment="Last renewal error, cleared on success",
        ),
    )
    op.create_index(
        op.f("ix_datasets_ttl_expires_at"),
        "datasets",
        ["ttl_expires_at"],
        unique=False,
    )

    # Backfill standalone anchors only: a dataset anchored individually was
    # written with the contract's full record budget, so its deadline is a fixed
    # offset from when it was anchored.
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT dataset_id, anchored_at FROM datasets "
            "WHERE status = 'anchored' AND batch_id IS NULL AND anchored_at IS NOT NULL "
            "AND ttl_expires_at IS NULL"
        )
    ).fetchall()
    for dataset_id, anchored_at in rows:
        bind.execute(
            sa.text("UPDATE datasets SET ttl_expires_at = :expires WHERE dataset_id = :dataset_id"),
            {"expires": anchored_at + ANCHORED_RECORD_LIFETIME, "dataset_id": dataset_id},
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_datasets_ttl_expires_at"), table_name="datasets")
    op.drop_column("datasets", "ttl_renewal_error")
    op.drop_column("datasets", "ttl_renewal_attempts")
    op.drop_column("datasets", "ttl_renewal_tx_hash")
    op.drop_column("datasets", "last_ttl_renewed_at")
    op.drop_column("datasets", "ttl_expires_at")
