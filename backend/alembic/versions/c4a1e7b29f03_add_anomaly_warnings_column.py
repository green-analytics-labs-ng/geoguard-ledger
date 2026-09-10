"""add anomaly_warnings column to datasets

Revision ID: c4a1e7b29f03
Revises: 07c7da391fc0
Create Date: 2026-09-10 09:41:12.004211

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4a1e7b29f03"
down_revision: str | Sequence[str] | None = "07c7da391fc0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "datasets",
        sa.Column(
            "anomaly_warnings",
            sa.JSON(),
            nullable=True,
            comment="Geochemical plausibility findings raised at upload time",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("datasets", "anomaly_warnings")
