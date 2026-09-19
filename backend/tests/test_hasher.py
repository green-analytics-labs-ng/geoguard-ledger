"""Tests for the CSV canonicalization and hashing service.

These pin the published canonicalization rules: the properties a third party
relies on when they re-hash a dataset and expect to reproduce the anchored
fingerprint. The normative rules live in SPECIFICATION.md.
"""

from app.services.hasher import compute_hash


def _hash_cell(cell: str) -> str:
    """Hash a one-column CSV containing a single cell."""
    return compute_hash(f"value\n{cell}\n")


def test_numbers_round_to_six_decimal_places() -> None:
    """7.1234567 hashes as 7.123457."""
    assert _hash_cell("7.1234567") == _hash_cell("7.123457")


def test_rounding_is_not_truncation() -> None:
    """The rounded form must not collide with the truncated form."""
    assert _hash_cell("7.1234567") != _hash_cell("7.123456")


def test_integer_and_decimal_forms_are_distinct() -> None:
    """5 and 5.0 currently hash differently: integers keep their written form."""
    assert _hash_cell("5") != _hash_cell("5.0")


def test_scientific_and_decimal_notation_are_distinct() -> None:
    """1e-3 and 0.001 currently hash differently: only decimals are converted."""
    assert _hash_cell("1e-3") != _hash_cell("0.001")
