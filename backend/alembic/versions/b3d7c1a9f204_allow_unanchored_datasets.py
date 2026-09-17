"""allow a dataset to be stored before it is anchored

Analysis no longer needs a wallet. `POST /datasets` now canonicalizes, hashes
and analyzes an upload and stores it as `analyzed` — no submitter, no
transaction — and `POST /datasets/{id}/anchor` binds the researcher's address
when the anchor transaction is built.

That requires `datasets.submitter_address` to accept NULL, and adds `analyzed`
to the set of statuses the column documents.

Existing rows need no backfill: every dataset written before this change
already carries the address it was anchored with. The constraint only has to
relax, not be rewritten.

Revision ID: b3d7c1a9f204
Revises: 849a9e96fe36
Create Date: 2026-09-17 09:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3d7c1a9f204"
down_revision: str | Sequence[str] | None = "849a9e96fe36"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Kept in step with the columns' comments in app/models/dataset.py, since
# Alembic compares comments when checking for drift.
SUBMITTER_COMMENT_ANALYZED = "Stellar public key (G...) of the researcher; NULL until anchored"
SUBMITTER_COMMENT_ANCHORED = "Stellar public key (G...) of the researcher"
STATUS_COMMENT_ANALYZED = "analyzed | pending | anchored | failed"
STATUS_COMMENT_ANCHORED = "pending | anchored | failed"


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "datasets",
        "submitter_address",
        existing_type=sa.String(length=56),
        nullable=True,
        existing_comment=SUBMITTER_COMMENT_ANCHORED,
        comment=SUBMITTER_COMMENT_ANALYZED,
    )
    op.alter_column(
        "datasets",
        "status",
        existing_type=sa.String(length=20),
        existing_comment=STATUS_COMMENT_ANCHORED,
        comment=STATUS_COMMENT_ANALYZED,
    )


def downgrade() -> None:
    """Downgrade schema."""
    # An unanchored dataset has nobody to attribute and no way to satisfy the
    # NOT NULL, so drop those rows rather than inventing an address. They were
    # never submitted, so nothing on-chain refers to them.
    op.execute("DELETE FROM datasets WHERE submitter_address IS NULL")
    op.alter_column(
        "datasets",
        "submitter_address",
        existing_type=sa.String(length=56),
        nullable=False,
        existing_comment=SUBMITTER_COMMENT_ANALYZED,
        comment=SUBMITTER_COMMENT_ANCHORED,
    )
    op.alter_column(
        "datasets",
        "status",
        existing_type=sa.String(length=20),
        existing_comment=STATUS_COMMENT_ANALYZED,
        comment=STATUS_COMMENT_ANCHORED,
    )
