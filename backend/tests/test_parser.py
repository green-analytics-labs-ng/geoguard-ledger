"""Unit tests for app.services.parser — direct, no HTTP layer."""

import json

import pytest

from app.services.parser import (
    SUPPORTED_EXTENSIONS,
    ParseError,
    get_extension,
    is_supported,
    parse_to_csv,
)

# ── SUPPORTED_EXTENSIONS ──────────────────────────────────────────


def test_supported_extensions_contains_csv_and_json():
    assert frozenset({".csv", ".json"}) == SUPPORTED_EXTENSIONS


def test_supported_extensions_is_frozenset():
    """Immutable — cannot be accidentally modified."""
    with pytest.raises(AttributeError):
        SUPPORTED_EXTENSIONS.add(".xml")  # type: ignore[union-attr]


# ── ParseError ────────────────────────────────────────────────────


def test_parse_error_inherits_geoguard_error():
    from app.core.exceptions import GeoGuardError

    assert issubclass(ParseError, GeoGuardError)


def test_parse_error_status_code():
    err = ParseError("test message")
    assert err.status_code == 400
    assert err.message == "test message"


# ── get_extension ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "filename, expected",
    [
        ("data.csv", ".csv"),
        ("data.json", ".json"),
        ("DATA.CSV", ".csv"),
        ("Data.JsOn", ".json"),
        ("my.geochem.dataset.csv", ".csv"),
        ("file", ""),
        ("noextension", ""),
        ("", ""),
        (".gitignore", ".gitignore"),
        (".csv", ".csv"),
        ("file.", "."),
        ("path/to/file.csv", ".csv"),
    ],
)
def test_get_extension(filename: str, expected: str):
    assert get_extension(filename) == expected


# ── is_supported ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "filename, expected",
    [
        ("data.csv", True),
        ("data.json", True),
        ("DATA.CSV", True),
        ("Data.JsOn", True),
        ("data.txt", False),
        ("data", False),
        ("", False),
        ("data.xml", False),
        ("data.csv.bak", False),  # .bak is not a supported extension
    ],
)
def test_is_supported(filename: str, expected: bool):
    assert is_supported(filename) == expected


# ── parse_to_csv — None / missing filename ────────────────────────


def test_parse_to_csv_none_filename():
    with pytest.raises(ParseError, match="Filename is required"):
        parse_to_csv(b"hello", None)


def test_parse_to_csv_empty_string_filename():
    """Empty string filename is falsy, triggers 'Filename is required'."""
    with pytest.raises(ParseError, match="Filename is required"):
        parse_to_csv(b"hello", "")


# ── parse_to_csv — unsupported extension ──────────────────────────


def test_parse_to_csv_unsupported_extension():
    with pytest.raises(ParseError, match="Unsupported file format"):
        parse_to_csv(b"hello", "data.txt")


def test_parse_to_csv_no_extension():
    with pytest.raises(ParseError, match="no extension"):
        parse_to_csv(b"hello", "data")


# ── parse_to_csv — CSV path ───────────────────────────────────────


def test_parse_to_csv_valid_csv():
    csv_bytes = b"col1,col2\n1,2\n3,4\n"
    result = parse_to_csv(csv_bytes, "data.csv")
    assert result == "col1,col2\n1,2\n3,4\n"


def test_parse_to_csv_non_utf8_csv():
    # Latin-1 bytes that are invalid UTF-8
    with pytest.raises(ParseError, match="UTF-8"):
        parse_to_csv(b"\xff\xfe\x00\x01", "data.csv")


# ── parse_to_csv — JSON path: happy paths ─────────────────────────


FLAT_JSON = json.dumps(
    [
        {"b": 2, "a": 1},
        {"b": 4, "a": 3},
    ]
).encode("utf-8")


def test_parse_to_csv_json_flat_array():
    result = parse_to_csv(FLAT_JSON, "data.json")
    # Columns must be sorted alphabetically: a, b
    assert result == "a,b\n1,2\n3,4\n"


def test_parse_to_csv_json_uppercase_extension():
    """Uppercase .JSON should be detected via case-insensitive get_extension."""
    result = parse_to_csv(FLAT_JSON, "DATA.JSON")
    assert result == "a,b\n1,2\n3,4\n"


def test_parse_to_csv_csv_uppercase_extension():
    """Uppercase .CSV should work the same as lowercase."""
    result = parse_to_csv(b"col1,col2\n1,2\n", "DATA.CSV")
    assert result == "col1,col2\n1,2\n"


WRAPPED_JSON = json.dumps(
    {
        "data": [
            {"b": 2, "a": 1},
            {"b": 4, "a": 3},
        ]
    }
).encode("utf-8")


def test_parse_to_csv_json_wrapped():
    result = parse_to_csv(WRAPPED_JSON, "data.json")
    assert result == "a,b\n1,2\n3,4\n"


# Keys out of order in the JSON should still produce sorted CSV columns.
UNORDERED_JSON = json.dumps(
    [
        {"z": 9, "m": 3, "a": 1},
    ]
).encode("utf-8")


def test_parse_to_csv_json_column_sorting():
    result = parse_to_csv(UNORDERED_JSON, "data.json")
    # Columns a, m, z (alphabetical)
    assert result.startswith("a,m,z\n")


# ── parse_to_csv — JSON path: determinism ─────────────────────────


def test_parse_to_csv_json_deterministic():
    """Same data, different key order → same CSV output."""
    a = json.dumps([{"b": 2, "a": 1}]).encode("utf-8")
    b = json.dumps([{"a": 1, "b": 2}]).encode("utf-8")
    assert parse_to_csv(a, "data.json") == parse_to_csv(b, "data.json")


def test_parse_to_csv_json_deterministic_wrapped():
    a = json.dumps({"data": [{"b": 2, "a": 1}]}).encode("utf-8")
    b = json.dumps({"data": [{"a": 1, "b": 2}]}).encode("utf-8")
    assert parse_to_csv(a, "data.json") == parse_to_csv(b, "data.json")


# ── parse_to_csv — JSON path: mixed / missing keys across records ─


INCONSISTENT_KEYS_JSON = json.dumps(
    [
        {"a": 1, "b": 2},
        {"b": 4, "c": 5},
        {"a": 7, "c": 8},
    ]
).encode("utf-8")


def test_parse_to_csv_json_inconsistent_keys():
    """Records with different keys → CSV with all columns (NaN → empty string)."""
    result = parse_to_csv(INCONSISTENT_KEYS_JSON, "data.json")
    lines = result.strip().split("\n")
    assert lines[0] == "a,b,c"
    # Row 0: a=1, b=2, c=NaN → "1,2,"
    assert lines[1] == "1.0,2.0,"
    # Row 1: a=NaN, b=4, c=5 → ",4.0,5.0"
    assert lines[2] == ",4.0,5.0"
    # Row 2: a=7, b=NaN, c=8 → "7.0,,8.0"
    assert lines[3] == "7.0,,8.0"


# ── parse_to_csv — JSON path: numeric & string values ─────────────


MIXED_TYPES_JSON = json.dumps(
    [
        {"name": "Site A", "ph": 7.2, "count": 3},
        {"name": "Site B", "ph": 8.1, "count": 5},
    ]
).encode("utf-8")


def test_parse_to_csv_json_mixed_types():
    result = parse_to_csv(MIXED_TYPES_JSON, "data.json")
    assert result == "count,name,ph\n3,Site A,7.2\n5,Site B,8.1\n"


# ── parse_to_csv — JSON path: single record ───────────────────────


SINGLE_RECORD_JSON = json.dumps([{"a": 1, "b": 2}]).encode("utf-8")


def test_parse_to_csv_json_single_record():
    result = parse_to_csv(SINGLE_RECORD_JSON, "data.json")
    assert result == "a,b\n1,2\n"


# ── parse_to_csv — JSON path: null values ─────────────────────────


NULL_VALUES_JSON = json.dumps(
    [
        {"a": 1, "b": None},
        {"a": None, "b": 2},
    ]
).encode("utf-8")


def test_parse_to_csv_json_null_values():
    result = parse_to_csv(NULL_VALUES_JSON, "data.json")
    lines = result.strip().split("\n")
    assert lines[0] == "a,b"
    assert lines[1] == "1.0,"
    assert lines[2] == ",2.0"


# ── parse_to_csv — JSON path: error cases ─────────────────────────


def test_parse_to_csv_json_invalid_syntax():
    with pytest.raises(ParseError, match="Invalid JSON"):
        parse_to_csv(b"not valid json at all", "data.json")


def test_parse_to_csv_json_non_utf8():
    with pytest.raises(ParseError, match="UTF-8"):
        parse_to_csv(b"\xff\xfe\x00\x01", "data.json")


def test_parse_to_csv_json_empty_array():
    with pytest.raises(ParseError, match="empty"):
        parse_to_csv(b"[]", "data.json")


def test_parse_to_csv_json_non_array_non_wrapped():
    with pytest.raises(ParseError, match="array of objects"):
        parse_to_csv(b'{"just": "a dict"}', "data.json")


def test_parse_to_csv_json_wrapped_data_not_array():
    with pytest.raises(ParseError, match="Expected a JSON array"):
        parse_to_csv(b'{"data": "not an array"}', "data.json")


def test_parse_to_csv_json_array_with_non_dicts():
    with pytest.raises(ParseError, match="must contain only objects"):
        parse_to_csv(b'[{"a": 1}, "string", 42]', "data.json")


def test_parse_to_csv_json_array_of_numbers():
    with pytest.raises(ParseError, match="must contain only objects"):
        parse_to_csv(b"[1, 2, 3]", "data.json")


def test_parse_to_csv_json_wrapped_empty_array():
    with pytest.raises(ParseError, match="empty"):
        parse_to_csv(b'{"data": []}', "data.json")


# ── parse_to_csv — CSV path: edge cases ────────────────────────────


def test_parse_to_csv_empty_csv():
    """Empty CSV content passes through — validation is downstream."""
    result = parse_to_csv(b"", "data.csv")
    assert result == ""


def test_parse_to_csv_csv_with_bom():
    """UTF-8 BOM should pass through as-is — downstream handles it."""
    result = parse_to_csv(b"\xef\xbb\xbfcol1,col2\n1,2\n", "data.csv")
    assert result.startswith("\ufeff")


# ── parse_to_csv — JSON path: data key present but not alone ──────


JSON_DATA_PLUS_EXTRA = json.dumps(
    {
        "data": [{"a": 1}],
        "meta": "ignored",
    }
).encode("utf-8")


def test_parse_to_csv_json_data_key_plus_extra_keys():
    """Extra top-level keys alongside 'data' are ignored."""
    result = parse_to_csv(JSON_DATA_PLUS_EXTRA, "data.json")
    assert result == "a\n1\n"
