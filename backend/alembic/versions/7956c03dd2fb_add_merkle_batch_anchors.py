"""add tables for Merkle batch anchoring

Revision ID: 7956c03dd2fb
Revises: c4a1e7b29f03
Create Date: 2026-09-12 09:46:41.267141

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7956c03dd2fb"
down_revision: str | Sequence[str] | None = "c4a1e7b29f03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "batches",
        sa.Column("batch_id", sa.String(length=36), nullable=False),
        sa.Column(
            "submitter_address",
            sa.String(length=56),
            nullable=False,
            comment="Stellar public key (G...) of the researcher",
        ),
        sa.Column(
            "merkle_root",
            sa.String(length=64),
            nullable=False,
            comment="SHA-256 hex Merkle root committing to every dataset in the batch",
        ),
        sa.Column(
            "leaf_count",
            sa.Integer(),
            nullable=False,
            comment="Number of dataset leaves committed to by the root",
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            comment="pending | anchored | failed",
        ),
        sa.Column(
            "unsigned_transaction_xdr",
            sa.Text(),
            nullable=True,
            comment="Unsigned Soroban transaction XDR (base64)",
        ),
        sa.Column(
            "signed_transaction_xdr",
            sa.Text(),
            nullable=True,
            comment="Researcher-signed transaction XDR (base64)",
        ),
        sa.Column(
            "stellar_tx_hash",
            sa.String(length=64),
            nullable=True,
            comment="Stellar transaction hash after successful submission",
        ),
        sa.Column(
            "ledger_number",
            sa.Integer(),
            nullable=True,
            comment="Stellar ledger number where the transaction was confirmed",
        ),
        sa.Column(
            "explorer_url",
            sa.String(length=256),
            nullable=True,
            comment="URL to view the transaction on Stellar Expert",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("anchored_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("batch_id"),
    )
    op.create_index(
        op.f("ix_batches_merkle_root"),
        "batches",
        ["merkle_root"],
        unique=True,
    )
    op.create_index(
        op.f("ix_batches_submitter_address"),
        "batches",
        ["submitter_address"],
        unique=False,
    )

    op.add_column(
        "datasets",
        sa.Column(
            "batch_id",
            sa.String(length=36),
            nullable=True,
            comment="Batch this dataset was anchored in, if any",
        ),
    )
    op.add_column(
        "datasets",
        sa.Column(
            "merkle_root",
            sa.String(length=64),
            nullable=True,
            comment="Hex Merkle root of the batch containing this dataset",
        ),
    )
    op.add_column(
        "datasets",
        sa.Column(
            "leaf_index",
            sa.Integer(),
            nullable=True,
            comment="Position of this dataset's hash within the batch leaves",
        ),
    )
    op.add_column(
        "datasets",
        sa.Column(
            "merkle_proof",
            sa.JSON(),
            nullable=True,
            comment="Bottom-up hex sibling hashes proving batch inclusion",
        ),
    )
    op.create_index(
        op.f("ix_datasets_batch_id"),
        "datasets",
        ["batch_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_datasets_merkle_root"),
        "datasets",
        ["merkle_root"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_datasets_merkle_root"), table_name="datasets")
    op.drop_index(op.f("ix_datasets_batch_id"), table_name="datasets")
    op.drop_column("datasets", "merkle_proof")
    op.drop_column("datasets", "leaf_index")
    op.drop_column("datasets", "merkle_root")
    op.drop_column("datasets", "batch_id")
    op.drop_index(op.f("ix_batches_submitter_address"), table_name="batches")
    op.drop_index(op.f("ix_batches_merkle_root"), table_name="batches")
    op.drop_table("batches")
