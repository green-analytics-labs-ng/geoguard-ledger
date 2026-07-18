"""File format parser. Supports CSV and JSON uploads.

Converts any supported format into a canonical CSV string for
compatibility with the existing hasher and anomaly detection pipeline.
"""

import io
import json
from typing import Any

import pandas as pd

from app.core.exceptions import GeoGuardError


class ParseError(GeoGuardError):
    """Raised when uploaded file cannot be parsed."""

    def __init__(self, message: str):
        super().__init__(message, status_code=400)


# Accepted file format extensions (lowercase, with leading dot)
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".csv", ".json"})


def get_extension(filename: str) -> str:
    """Extract lowercase file extension from a filename."""
    if "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()


def is_supported(filename: str) -> bool:
    """Check if the filename has a supported extension."""
    return get_extension(filename) in SUPPORTED_EXTENSIONS


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

    if not all(isinstance(r, dict) for r in records):
        raise ParseError("JSON array must contain only objects")

    # Build DataFrame and re-export to canonical CSV
    try:
        df = pd.DataFrame(records)
    except Exception as exc:
        raise ParseError(f"Failed to convert JSON to tabular data: {exc}") from exc

    # Sort columns alphabetically for deterministic output
    df = df.reindex(columns=sorted(df.columns))

    output = io.StringIO()
    df.to_csv(output, index=False)
    csv_str = output.getvalue()

    # Strip unnecessary ".0" from integer values that pandas floatifies.
    # A value like "3.0\n" after a comma or at line start is an integer
    # that pandas cast to float64. Match whole tokens so "3.0" doesn't
    # become "3" inside "3.05".
    import re as _re

    csv_str = _re.sub(r"(?<=,|^)(\d+)\.0(?=\n|,)", r"\1", csv_str)
    return csv_str
