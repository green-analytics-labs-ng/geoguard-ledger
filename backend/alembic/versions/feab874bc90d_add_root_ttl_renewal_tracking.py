"""add root ttl renewal tracking

Adds the bookkeeping the root TTL renewal job needs: when each anchored Merkle
root expires, what the last renewal did, and whether it is failing repeatedly.

Existing anchored roots are backfilled so they are eligible for renewal. Without
that they would have a NULL deadline, never be selected, and expire silently —
which is the very failure this migration exists to prevent.

Revision ID: feab874bc90d
Revises: 7956c03dd2fb
Create Date: 2026-09-12 11:15:50.089006

"""

from collections.abc import Sequence
from datetime import timedelta

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "feab874bc90d"
down_revision: str | Sequence[str] | None = "7956c03dd2fb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Mirrors ROOT_TTL_EXTEND_TO in contracts/geoguard-ledger/src/storage.rs
# (3,110,400 ledgers at ~5s each). Frozen here on purpose: a migration must not
# follow a constant that can change later.
ANCHORED_ROOT_LIFETIME = timedelta(days=180)


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "batches",
        sa.Column(
            "root_ttl_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When the on-chain root entry expires unless renewed",
        ),
    )
    op.add_column(
        "batches",
        sa.Column(
            "last_ttl_renewed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last successful root TTL renewal",
        ),
    )
    op.add_column(
        "batches",
        sa.Column(
            "ttl_renewal_tx_hash",
            sa.String(length=64),
            nullable=True,
            comment="Transaction hash of the most recent successful renewal",
        ),
    )
    op.add_column(
        "batches",
        sa.Column(
            "ttl_renewal_attempts",
            sa.Integer(),
            server_default="0",
            nullable=False,
            comment="Renewal attempts, so a root failing repeatedly is visible",
        ),
    )
    op.add_column(
        "batches",
        sa.Column(
            "ttl_renewal_error",
            sa.Text(),
            nullable=True,
            comment="Last renewal error, cleared on success",
        ),
    )
    op.create_index(
        op.f("ix_batches_root_ttl_expires_at"),
        "batches",
        ["root_ttl_expires_at"],
        unique=False,
    )

    # Backfill: an anchored root was written with the contract's full TTL budget,
    # so its deadline is a fixed offset from when it was anchored.
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT batch_id, anchored_at FROM batches "
            "WHERE status = 'anchored' AND anchored_at IS NOT NULL "
            "AND root_ttl_expires_at IS NULL"
        )
    ).fetchall()
    for batch_id, anchored_at in rows:
        bind.execute(
            sa.text("UPDATE batches SET root_ttl_expires_at = :expires WHERE batch_id = :batch_id"),
            {"expires": anchored_at + ANCHORED_ROOT_LIFETIME, "batch_id": batch_id},
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_batches_root_ttl_expires_at"), table_name="batches")
    op.drop_column("batches", "ttl_renewal_error")
    op.drop_column("batches", "ttl_renewal_attempts")
    op.drop_column("batches", "ttl_renewal_tx_hash")
    op.drop_column("batches", "last_ttl_renewed_at")
    op.drop_column("batches", "root_ttl_expires_at")
