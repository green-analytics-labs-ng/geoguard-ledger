"""Regression tests for JSON -> CSV type preservation.

The JSON parser must not coerce integers into floats. Before this was fixed,
a DataFrame round-trip turned ``3`` into ``3.0`` whenever a column contained a
missing value, so the same data uploaded as JSON and as CSV produced different
SHA-256 hashes - defeating the purpose of deterministic anchoring.
"""

import json

from app.services.hasher import compute_hash
from app.services.parser import parse_to_csv


def _json(*records: dict[str, object]) -> bytes:
    return json.dumps(list(records)).encode("utf-8")


# ── Integers stay integers ────────────────────────────────────────


def test_integers_are_preserved() -> None:
    assert parse_to_csv(_json({"count": 3}, {"count": 5}), "data.json") == "count\n3\n5\n"


def test_integers_survive_missing_keys() -> None:
    """A missing key must not float-ify the remaining integer column."""
    payload = _json({"a": 1, "b": 2}, {"b": 4, "c": 5})
    assert parse_to_csv(payload, "data.json") == "a,b,c\n1,2,\n,4,5\n"


def test_integers_survive_explicit_nulls() -> None:
    payload = _json({"a": 1, "b": None}, {"a": None, "b": 2})
    assert parse_to_csv(payload, "data.json") == "a,b\n1,\n,2\n"


def test_explicit_floats_keep_their_decimal_point() -> None:
    payload = _json({"ph": 7.2, "ratio": 1.0})
    assert parse_to_csv(payload, "data.json") == "ph,ratio\n7.2,1.0\n"


# ── Numeric formatting ────────────────────────────────────────────


def test_small_and_large_floats_avoid_scientific_notation() -> None:
    result = parse_to_csv(_json({"tiny": 1e-07, "big": 1e20}), "data.json")
    assert result == "big,tiny\n100000000000000000000,0.0000001\n"


def test_non_finite_values_render_as_empty_cells() -> None:
    # json.loads accepts these literals even though strict JSON does not.
    payload = b'[{"a": NaN, "b": Infinity, "c": 1}]'
    assert parse_to_csv(payload, "data.json") == "a,b,c\n,,1\n"


# ── Hash equivalence with CSV ─────────────────────────────────────


def test_json_and_csv_of_the_same_data_hash_identically() -> None:
    """The core guarantee: the upload format must not change the hash."""
    csv_text = "a,b\n1,\n,2\n"
    json_bytes = _json({"a": 1}, {"b": 2})

    csv_hash = compute_hash(parse_to_csv(csv_text.encode("utf-8"), "data.csv"))
    json_hash = compute_hash(parse_to_csv(json_bytes, "data.json"))

    assert csv_hash == json_hash


def test_hash_is_stable_across_key_order() -> None:
    a = _json({"b": 2, "a": 1})
    b = _json({"a": 1, "b": 2})
    assert parse_to_csv(a, "data.json") == parse_to_csv(b, "data.json")


# ── Cell quoting ──────────────────────────────────────────────────


def test_cells_containing_separators_are_quoted() -> None:
    payload = _json({"city": "Zaria, Kaduna", "note": 'say "hi"'})
    assert parse_to_csv(payload, "data.json") == 'city,note\n"Zaria, Kaduna","say ""hi"""\n'


def test_nested_values_are_serialised_deterministically() -> None:
    payload = _json({"meta": {"b": 2, "a": 1}})
    assert parse_to_csv(payload, "data.json") == 'meta\n"{""a"":1,""b"":2}"\n'
