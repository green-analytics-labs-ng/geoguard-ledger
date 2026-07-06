#!/usr/bin/env python3
"""Seed the database with sample datasets for development and testing."""

import csv
import hashlib
import io
import uuid
from datetime import datetime, timezone

SAMPLE_DATA = """sample_id,latitude,longitude,pH,conductivity,dissolved_oxygen,temperature
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


def main():
    # Normalize and hash the sample data
    text = SAMPLE_DATA.strip().replace("\r\n", "\n")
    dataset_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

    print(f"Sample dataset hash: {dataset_hash}")
    print(f"Rows: {len(text.splitlines()) - 1}")
    print(f"Dataset ID: {uuid.uuid4()}")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print()
    print("Database seeding not yet connected — placeholder script.")


if __name__ == "__main__":
    main()
