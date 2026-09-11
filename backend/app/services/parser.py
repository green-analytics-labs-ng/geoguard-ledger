"""File format parser. Supports CSV, JSON and XML uploads.

CSV and JSON are converted into a canonical CSV string for compatibility with
hasher and anomaly detection pipeline. JSON values are serialized without type
coercion: integers stay integers, so the same data uploaded as JSON and as CSV
hashes identically.

XML is different: it is canonicalized into deterministic XML bytes (see
``canonicalize_xml``) rather than converted to CSV, because a tabular
round-trip would discard structure and attribute information.
"""

import csv
import io
import json
import math
import xml.etree.ElementTree as ET
from decimal import Decimal
from typing import Any, Literal

from app.core.exceptions import GeoGuardError


class ParseError(GeoGuardError):
    """Raised when uploaded file cannot be parsed."""

    def __init__(self, message: str):
        super().__init__(message, status_code=400)


FileFormat = Literal["csv", "json", "xml"]

# Single source of truth for accepted extensions and their format names.
_EXTENSION_TO_FORMAT: dict[str, FileFormat] = {
    ".csv": "csv",
    ".json": "json",
    ".xml": "xml",
}

# Accepted file format extensions (lowercase, with leading dot)
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(_EXTENSION_TO_FORMAT)


def get_extension(filename: str) -> str:
    """Extract lowercase file extension from a filename."""
    if "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()


def is_supported(filename: str) -> bool:
    """Check if the filename has a supported extension."""
    return get_extension(filename) in SUPPORTED_EXTENSIONS


def describe_supported_formats() -> str:
    """Human-readable list of accepted extensions, e.g. ``'.csv, .json, .xml'``."""
    return ", ".join(sorted(SUPPORTED_EXTENSIONS))


def get_file_format(filename: str | None) -> FileFormat:
    """Return the canonical format name for a supported filename.

    Raises:
        ParseError: If the filename is missing or has an unsupported extension.
    """
    if not filename:
        raise ParseError("Filename is required to detect file format")

    ext = get_extension(filename)
    file_format = _EXTENSION_TO_FORMAT.get(ext)

    if file_format is None:
        raise ParseError(
            "Unsupported file format: "
            + repr(ext if ext else "no extension")
            + ". Accepted formats: "
            + describe_supported_formats()
        )

    return file_format


def parse_to_csv(content: bytes, filename: str | None) -> str:
    """Parse uploaded file content into a canonical CSV string.

    Args:
        content: Raw file bytes.
        filename: Original filename (used to detect format via extension).

    Returns:
        Canonical CSV string suitable for hashing and anomaly detection.

    Raises:
        ParseError: If the file format is unsupported or content is invalid.
    """
    if not filename:
        raise ParseError("Filename is required to detect file format")

    ext = get_extension(filename)

    if ext == ".csv":
        return _parse_csv(content)
    elif ext == ".json":
        return _parse_json(content)
    elif ext == ".xml":
        # XML is not converted to CSV: it is canonicalized and hashed as XML,
        # then flattened for analysis by the anomaly service. See
        # app.services.ingest.process_upload.
        raise ParseError(
            "XML files are canonicalized rather than converted to CSV; "
            "use app.services.ingest.process_upload()"
        )
    else:
        raise ParseError(
            "Unsupported file format: "
            + repr(ext if ext else "no extension")
            + ". Accepted formats: "
            + ", ".join(sorted(SUPPORTED_EXTENSIONS))
        )


def _parse_csv(content: bytes) -> str:
    """Decode and return CSV content as a UTF-8 string."""
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ParseError(f"File must be UTF-8 encoded: {exc}") from exc


def _parse_json(content: bytes) -> str:
    """Parse JSON content and convert to a canonical CSV string.

    Supported JSON structures:
        - Array of objects:  [{"col1": val1, "col2": val2}, ...]
        - Object with ``data`` key:  {"data": [{"col1": val1}, ...]}

    Columns are sorted alphabetically so that the resulting CSV is
    deterministic regardless of key ordering in the JSON.

    Cells are rendered from their JSON types rather than via a DataFrame, so
    an integer ``3`` stays ``3`` (never ``3.0``) and missing keys stay empty
    strings. This keeps JSON- and CSV-originated hashes identical.
    """
    try:
        json_text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ParseError(f"JSON file must be UTF-8 encoded: {exc}") from exc

    try:
        raw: Any = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise ParseError(f"Invalid JSON: {exc}") from exc

    # Normalize to a list of record dicts
    if isinstance(raw, list):
        records = raw
    elif isinstance(raw, dict) and "data" in raw:
        records = raw["data"]
    else:
        raise ParseError(
            "JSON must contain either an array of objects or an object "
            "with a 'data' key containing an array of objects"
        )

    if not isinstance(records, list):
        raise ParseError(f"Expected a JSON array of records, got {type(records).__name__}")

    if len(records) == 0:
        raise ParseError("JSON data array is empty")

    rows = _as_rows(records)

    # Union of every key across all records, sorted for determinism.
    columns = sorted({key for row in rows for key in row})

    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_render_cell(row.get(column)) for column in columns])

    return output.getvalue()


# ── XML path ──────────────────────────────────────────────────────


def canonicalize_xml(content: bytes) -> bytes:
    """Canonicalize an XML document into deterministic UTF-8 bytes.

    The rules are deliberately simple - this is not full W3C C14N - but they
    are reproducible, so two XML files that carry the same information produce
    the same bytes and therefore the same hash:

    1. Comments and processing instructions are dropped.
    2. Attribute names are sorted alphabetically within every element.
    3. Whitespace-only text/tail nodes (pretty-printing indentation) are
       removed, while text that carries data is preserved verbatim.
    4. Empty elements use their short form (``<a/>``).
    5. Output is UTF-8 with no BOM and no XML declaration.

    Args:
        content: Raw file bytes. A leading UTF-8 BOM is tolerated.

    Returns:
        Canonical UTF-8 bytes suitable for hashing.

    Raises:
        ParseError: If the bytes are not UTF-8 or the document is malformed.
    """
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ParseError(f"XML file must be UTF-8 encoded: {exc}") from exc

    try:
        # ElementTree discards comments and processing instructions by default.
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ParseError(f"Malformed XML: {exc}") from exc

    canonical: bytes = ET.tostring(
        _canonicalize_element(root),
        encoding="utf-8",
        xml_declaration=False,
        short_empty_elements=True,
    )
    return canonical


def _canonicalize_element(element: ET.Element) -> ET.Element:
    """Rebuild an element with sorted attributes and no insignificant whitespace."""
    rebuilt = ET.Element(element.tag, dict(sorted(element.attrib.items())))
    rebuilt.text = _drop_insignificant_whitespace(element.text)

    for child in element:
        rebuilt_child = _canonicalize_element(child)
        rebuilt_child.tail = _drop_insignificant_whitespace(child.tail)
        rebuilt.append(rebuilt_child)

    return rebuilt


def _drop_insignificant_whitespace(value: str | None) -> str | None:
    """Return ``None`` for whitespace-only text so indentation is not serialized."""
    if value is None or not value.strip():
        return None
    return value


def _as_rows(records: list[Any]) -> list[dict[str, Any]]:
    """Validate and normalise JSON records into a list of string-keyed dicts."""
    rows: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            raise ParseError("JSON array must contain only objects")
        rows.append({str(key): value for key, value in record.items()})
    return rows


def _render_cell(value: Any) -> str:
    """Render a JSON value as a CSV cell without coercion.

    Integers are rendered verbatim so they cannot be float-ified into ``3.0``,
    which would break hash equivalence between JSON and CSV uploads.
    """
    if value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _render_float(value)
    if isinstance(value, str):
        return value
    # Nested objects/arrays: canonical JSON keeps the cell deterministic.
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _render_float(value: float) -> str:
    """Render a float without an exponent so the CSV stays stable and readable.

    ``Decimal(repr(value))`` keeps the shortest round-trippable representation
    and ``format(..., "f")`` expands it, so ``1e-07`` becomes ``0.0000001``
    instead of leaking scientific notation into the cell.
    """
    if not math.isfinite(value):
        # JSON has no representation for NaN/Infinity; drop them like empty cells.
        return ""

    return format(Decimal(repr(value)), "f")
