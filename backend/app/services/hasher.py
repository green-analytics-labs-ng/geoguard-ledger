"""SHA-256 hashing service with CSV canonicalization.

Canonicalization v1 (``CANONICALIZATION_VERSION``) makes a dataset's
fingerprint reproducible by any third party:

- RFC 4180-compliant CSV parsing
- UTF-8 encoding (no BOM)
- Line endings normalized to \\n
- Every cell normalized to Unicode NFC
- Leading and trailing whitespace stripped from every cell
- Integer, decimal, and scientific-notation cells rendered as one canonical
  decimal form, rounded half-even to 6 decimal places
- Row order preserved exactly as it appears in the file
"""

import csv
import hashlib
import io
import re
import unicodedata
from decimal import Decimal, InvalidOperation

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


# A numeric cell in JSON-number form: optional sign, no leading zeros in the
# integer part, optional fraction, optional exponent. Leading zeros are
# deliberately excluded so identifiers such as "0001" are never rewritten as
# the number 1.
_NUMERIC_RE = re.compile(r"^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?$")

_DECIMAL_PLACES = 6
_ZERO = "0.000000"


def _canonicalize_cell(cell: str) -> str:
    """Canonicalize a single CSV cell."""
    cell = unicodedata.normalize("NFC", cell).strip()
    if not _NUMERIC_RE.match(cell):
        return cell

    # Integers, decimals, and scientific notation collapse into one numeric
    # form: a plain decimal rounded half-even to a fixed number of places. So
    # "5", "5.0", "1e-3" and "0.001" cannot produce different hashes.
    try:
        rendered = format(Decimal(cell), f".{_DECIMAL_PLACES}f")
    except (InvalidOperation, ValueError):
        return cell

    # A value that rounds to zero has no meaningful sign (-0 -> 0).
    if rendered.startswith("-") and set(rendered[1:]) <= {".", "0"}:
        return _ZERO
    return rendered
