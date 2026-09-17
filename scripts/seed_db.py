#!/usr/bin/env python3
"""Seed the database with sample datasets for development and testing.

Rows are produced by running real sample data through the same hashing and
anomaly-detection pipeline the API uses, so the seeded records are valid
datasets rather than fabricated rows.

Usage:
    # From the backend directory (matches the documented dev workflow):
    cd backend && uv run python ../scripts/seed_db.py

    # Or from the repository root with the backend virtualenv active:
    python scripts/seed_db.py

The database must already be migrated (`cd backend && uv run alembic upgrade
head`), which `scripts/setup_dev.sh` does. The script will not create the schema
itself — see `_require_schema` for why.

The script is idempotent: a dataset whose hash already exists is skipped, so it
is safe to run repeatedly against the same database.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

# Make `app` importable when the script is run directly from the repo root.
REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.exc import ProgrammingError  # noqa: E402

from app.db.session import AsyncSessionLocal, async_engine  # noqa: E402
from app.models.dataset import Dataset  # noqa: E402
from app.services.anomaly import run_anomaly_detection  # noqa: E402
from app.services.hasher import compute_hash  # noqa: E402

# Placeholder submitter for seeded rows. This is deliberately not a real
# keypair: seeding writes directly to the database and never signs anything.
SEED_SUBMITTER_ADDRESS = "G" + "A" * 55

SAMPLE_CSV = """sample_id,latitude,longitude,pH,conductivity,dissolved_oxygen,temperature
S001,34.052200,-118.243700,7.20,450.00,8.50,22.10
S002,34.052500,-118.244000,7.15,452.00,8.30,22.30
S003,34.052800,-118.244300,7.18,448.00,8.70,22.00
S004,34.053100,-118.244600,7.22,455.00,8.40,22.20
S005,34.053400,-118.244900,7.19,449.00,8.60,22.40
S006,34.053700,-118.245200,7.21,451.00,8.45,22.15
S007,34.054000,-118.245500,7.17,453.00,8.55,22.25
S008,34.054300,-118.245800,7.23,450.00,8.35,22.05
S009,34.054600,-118.246100,7.16,447.00,8.65,22.35
S010,34.054900,-118.246400,7.20,454.00,8.50,22.10
"""

ANOMALOUS_CSV = """sample_id,latitude,longitude,pH,conductivity,dissolved_oxygen,temperature
S001,34.052200,-118.243700,7.20,450.00,8.50,22.10
S002,34.052500,-118.244000,7.15,452.00,8.30,22.30
S003,34.052800,-118.244300,7.18,448.00,8.70,22.00
S004,34.053100,-118.244600,7.22,455.00,8.40,22.20
S005,34.053400,-118.244900,7.19,449.00,8.60,22.40
S006,34.050000,-118.250000,9.99,9999.00,0.10,999.99
"""

# A dataset with a physically impossible reading, used to exercise the
# geochemical plausibility warnings in the UI.
OUT_OF_RANGE_CSV = """sample_id,latitude,longitude,pH,conductivity,dissolved_oxygen,temperature
S001,34.052200,-118.243700,7.20,450.00,8.50,22.10
S002,34.052500,-118.244000,7.15,452.00,8.30,22.30
S003,34.052800,-118.244300,3.40,-118.00,8.70,22.00
S004,34.053100,-118.244600,20.50,455.00,8.40,22.20
S005,34.053400,-118.244900,7.19,449.00,8.60,22.40
S006,34.053700,-118.245200,7.21,451.00,8.45,22.15
"""


def _build_seed_rows() -> list[dict[str, Any]]:
    """Run each sample dataset through the real pipeline and build ORM rows."""
    # `analyzed` is a dataset that has been hashed and scored but never
    # anchored: no address is attached to it, and no transaction exists for it.
    sources: list[tuple[str, str, str]] = [
        ("groundwater-baseline.csv", SAMPLE_CSV, "analyzed"),
        ("nitrate-spike-anomaly.csv", ANOMALOUS_CSV, "anchored"),
        ("impossible-readings.csv", OUT_OF_RANGE_CSV, "analyzed"),
    ]

    rows: list[dict[str, Any]] = []
    for name, content, record_status in sources:
        dataset_hash = compute_hash(content)
        result = run_anomaly_detection(content)

        rows.append(
            {
                # The address binds when the anchor transaction is built, so an
                # analyzed dataset does not have one yet.
                "submitter_address": (
                    SEED_SUBMITTER_ADDRESS if record_status == "anchored" else None
                ),
                "dataset_hash": dataset_hash,
                "status": record_status,
                "anomaly_score": result["score"],
                "anomaly_flags": result["flags"],
                "model_version": result["model_version"],
                "anomaly_summary": result["summary"],
                "anomaly_warnings": result.get("warnings", []),
                "unsigned_transaction_xdr": None,
                "signed_transaction_xdr": None,
            }
        )
        print(f"  prepared {name}: {result['summary']}")

    return rows


async def _require_schema() -> None:
    """Stop with a fixable message when migrations have not been applied.

    The schema belongs to Alembic. Creating the tables here would leave them
    with no recorded revision, and `alembic upgrade head` would then refuse to
    touch a database that already has tables — the state that made a dev
    database unupgradable.
    """
    try:
        async with async_engine.connect() as conn:
            await conn.execute(select(Dataset.dataset_id).limit(1))
    except ProgrammingError as exc:
        print(
            "The database has no schema yet. Run the migrations first:\n"
            "    cd backend && uv run alembic upgrade head",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc


async def seed() -> int:
    """Insert sample datasets, skipping any that already exist.

    Returns:
        The number of datasets inserted.
    """
    await _require_schema()

    inserted = 0
    async with AsyncSessionLocal() as session:
        for row in _build_seed_rows():
            existing = await session.execute(
                select(Dataset.dataset_id).where(
                    Dataset.dataset_hash == row["dataset_hash"]
                )
            )
            if existing.scalar_one_or_none() is not None:
                print(f"  skip  {row['dataset_hash'][:12]}... already seeded")
                continue

            session.add(Dataset(**row))
            inserted += 1
            print(f"  add   {row['dataset_hash'][:12]}... ({row['status']})")

        await session.commit()

    await async_engine.dispose()
    return inserted


def main() -> None:
    print("Seeding GeoGuard Ledger database...")
    inserted = asyncio.run(seed())
    print(f"Done. Inserted {inserted} dataset(s).")


if __name__ == "__main__":
    main()
