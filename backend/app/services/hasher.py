"""SHA-256 hashing service with CSV canonicalization.

Canonicalization v1 (``CANONICALIZATION_VERSION``) makes a dataset's
fingerprint reproducible by any third party:

- RFC 4180-compliant CSV parsing
- UTF-8 encoding (no BOM)
- Line endings normalized to \\n
- Every cell normalized to Unicode NFC
- Leading and trailing whitespace stripped from every cell
- Numeric cells rounded half-even to 6 decimal places
- Row order preserved exactly as it appears in the file
"""

import csv
import hashlib
import io
import re
import unicodedata

# Version of the canonicalization rules implemented here. Any change to a rule
# re-hashes every dataset, and a hash anchored under an older rule set can no
# longer be reproduced by this code, so the version is advertised in API
# responses: a verifier uses it to know which rule set a stored hash came from.
CANONICALIZATION_VERSION = "1"


def compute_hash(csv_text: str) -> str:
    """Compute SHA-256 hash over canonicalized CSV content."""
    canonicalized = _canonicalize(csv_text)
    return compute_hash_bytes(canonicalized.encode("utf-8"))


def compute_hash_bytes(content: bytes) -> str:
    """Compute SHA-256 over bytes that are already in canonical form.

    Used by formats whose canonical representation is not CSV (currently XML,
    which is canonicalized by ``app.services.parser.canonicalize_xml``).
    """
    return hashlib.sha256(content).hexdigest()


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
    cell = unicodedata.normalize("NFC", cell).strip()
    if _NUMERIC_RE.match(cell) and "." in cell:
        try:
            value = float(cell)
            cell = f"{value:.6f}"
        except ValueError:
            pass
    return cell
