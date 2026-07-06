"""SHA-256 hashing service with CSV canonicalization.

Canonicalization rules ensure deterministic hashing:
- RFC 4180-compliant CSV parsing
- UTF-8 encoding (no BOM)
- Line endings normalized to \\n
- Numeric columns truncated to 6 decimal places
- Trailing whitespace stripped from all cells
"""

import csv
import hashlib
import io
import re


def compute_hash(csv_text: str) -> str:
    """Compute SHA-256 hash over canonicalized CSV content."""
    canonicalized = _canonicalize(csv_text)
    return hashlib.sha256(canonicalized.encode("utf-8")).hexdigest()


def _canonicalize(csv_text: str) -> str:
    """Apply canonicalization rules to CSV content."""
    # Normalize line endings
    text = csv_text.replace("\r\n", "\n").replace("\r", "\n")

    # Strip BOM if present
    text = text.lstrip("\ufeff")

    # Parse and re-serialize to normalize
    output = io.StringIO()
    reader = csv.reader(io.StringIO(text))
    writer = csv.writer(output, lineterminator="\n")

    for row in reader:
        normalized_row = [_canonicalize_cell(cell) for cell in row]
        writer.writerow(normalized_row)

    return output.getvalue()


_NUMERIC_RE = re.compile(r"^-?\d+(?:\.\d+)?$")


def _canonicalize_cell(cell: str) -> str:
    """Canonicalize a single CSV cell."""
    cell = cell.strip()
    if _NUMERIC_RE.match(cell) and "." in cell:
        try:
            value = float(cell)
            cell = f"{value:.6f}"
        except ValueError:
            pass
    return cell
