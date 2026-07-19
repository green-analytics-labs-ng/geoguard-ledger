#!/usr/bin/env python3
"""Seed the database with sample datasets for development and testing.

Usage:
    uv run python scripts/seed_db.py
"""

import asyncio
import hashlib
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(_BACKEND))

from app.db.session import AsyncSessionLocal
from app.models.dataset import Dataset

SAMPLE_CSV = """sample_id,latitude,longitude,pH,conductivity,dissolved_oxygen,temperature
S001,34.052200,-118.243700,7.20,450.00,8.50,22.10
S002,34.052500,-118.244000,7.15,452.00,8.30,22.30
S003,34.052800,-118.244300,7.18,448.00,8.70,22.00
S004,34.053100,-118.244600,7.22,455.00,8.40,22.20
S005,34.053400,-118.244900,7.19,449.00,8.60,22.40
"""

DATASETS: list[dict[str, object]] = [
    {
        "submitter_address": "GCYZFJLXVXHL3RN2XECSLGTS2NPMHWGJUYTZWKNNELRML56NBJY5YRRG",
        "anomaly_score": 0.0,
        "model_version": "isoforest-v1",
    },
    {
        "submitter_address": "GCYZFJLXVXHL3RN2XECSLGTS2NPMHWGJUYTZWKNNELRML56NBJY5YRRG",
        "anomaly_score": 0.2,
        "model_version": "isoforest-v1",
    },
    {
        "submitter_address": "GBV4ZDEPNQ2FSPIODQ6WVBBS2Y5EYAH2KQH33LK6JYKGTLJPRZ7VLV7H",
        "anomaly_score": 0.4,
        "model_version": "isoforest-v2",
    },
]


async def seed() -> None:
    canonical_csv = SAMPLE_CSV.strip().replace("\r\n", "\n")

    seeded = 0
    async with AsyncSessionLocal() as session:
        for i, meta in enumerate(DATASETS):
            unique_hash = hashlib.sha256(
                (canonical_csv + str(i)).encode("utf-8"),
            ).hexdigest()

            record = Dataset(
                dataset_hash=unique_hash,
                submitter_address=str(meta["submitter_address"]),
                status="pending",
                anomaly_score=float(meta["anomaly_score"]),
                anomaly_flags=[],
                model_version=str(meta["model_version"]),
                anomaly_summary=f"Sample dataset {i + 1}",
            )
            session.add(record)
            seeded += 1

        await session.commit()

    print(f"Seeded {seeded} sample datasets into the database.")


def main() -> None:
    print("Seeding database with sample datasets ...")
    asyncio.run(seed())


if __name__ == "__main__":
    main()
