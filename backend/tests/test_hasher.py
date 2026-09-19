"""Tests for the CSV canonicalization and hashing service.

These pin the published canonicalization rules: the properties a third party
relies on when they re-hash a dataset and expect to reproduce the anchored
fingerprint. The normative rules, and the test vectors asserted below, live in
docs/canonicalization.md.
"""

import pytest

from app.services.hasher import CANONICALIZATION_VERSION, _canonicalize_cell, compute_hash


def _hash_cell(cell: str) -> str:
    """Hash a one-column CSV containing a single cell."""
    return compute_hash(f"value\n{cell}\n")


def test_canonicalization_version_is_published() -> None:
    """The rule set behind every hash carries a version a verifier can read."""
    assert CANONICALIZATION_VERSION == "1"


def test_numbers_round_to_six_decimal_places() -> None:
    """7.1234567 hashes as 7.123457."""
    assert _hash_cell("7.1234567") == _hash_cell("7.123457")


def test_rounding_is_not_truncation() -> None:
    """The rounded form must not collide with the truncated form."""
    assert _hash_cell("7.1234567") != _hash_cell("7.123456")


def test_integer_and_decimal_forms_are_equivalent() -> None:
    """5 and 5.0 are the same number, so they hash identically."""
    assert _hash_cell("5") == _hash_cell("5.0")


def test_scientific_and_decimal_notation_are_equivalent() -> None:
    """1e-3 and 0.001 are the same number, so they hash identically."""
    assert _hash_cell("1e-3") == _hash_cell("0.001")


def test_leading_zero_cells_are_identifiers_not_numbers() -> None:
    """A cell like 0001 is an identifier, so it is never rewritten as 1."""
    assert _hash_cell("0001") != _hash_cell("1")
    assert _hash_cell("0001") == _hash_cell("0001")


def test_composed_and_decomposed_unicode_are_equivalent() -> None:
    """NFC and NFD forms of the same text hash identically."""
    nfc = "\u00e9"  # é as a single code point
    nfd = "e\u0301"  # same glyph, e followed by a combining acute accent
    assert nfc != nfd
    assert _hash_cell(nfc) == _hash_cell(nfd)


def test_row_order_is_significant() -> None:
    """Rows keep their file order; swapping them must change the hash."""
    assert compute_hash("value\n1\n2\n") != compute_hash("value\n2\n1\n")


def test_out_of_range_exponents_are_left_as_text() -> None:
    """An exponent Decimal cannot represent falls back to the raw cell.

    The form still matches the numeric pattern, but it is not a number any
    implementation could render, so rewriting it would be worse than leaving it
    alone — and it must never crash a hash.
    """
    cell = "1e99999999999999999999"
    assert _canonicalize_cell(cell) == cell


def test_negative_zero_has_no_sign() -> None:
    """A value that rounds to zero collapses to the same cell as positive zero."""
    assert _canonicalize_cell("-0") == "0.000000"
    assert _canonicalize_cell("-0.0000001") == "0.000000"
    assert _hash_cell("-0.0000001") == _hash_cell("0")


# ── Published test vectors ────────────────────────────────────────
# Mirrors the table in docs/canonicalization.md. A mismatch means a hash
# anchored under v1 can no longer be reproduced by the current code, so the
# only correct response is to bump CANONICALIZATION_VERSION and regenerate
# both the table and these vectors.
PUBLISHED_VECTORS: dict[str, str] = {
    "value\n5\n": "fa0f3c48a79985ff55647a782576d90c88d5708cccef42f0510f007ce9eab972",
    "value\n5.0\n": "fa0f3c48a79985ff55647a782576d90c88d5708cccef42f0510f007ce9eab972",
    "\ufeffvalue\r\n 5 \r\n": "fa0f3c48a79985ff55647a782576d90c88d5708cccef42f0510f007ce9eab972",
    "value\n1e-3\n": "c3ac2598c41e864d5c6e708bfaebdbd10ab8a6359aa04c95395e9be2ff6a0ad8",
    "value\n0.001\n": "c3ac2598c41e864d5c6e708bfaebdbd10ab8a6359aa04c95395e9be2ff6a0ad8",
    "value\n7.1234567\n": "ca2ca79fec9672254626538d657f475c8db16b9a6ffa7d3afdce7a3311be7020",
    "value\n\u00e9\n": "623953c55233048064eec0e74cfa54bf9bda8eb1c68ca593e7638874ffc38c08",
    "value\ne\u0301\n": "623953c55233048064eec0e74cfa54bf9bda8eb1c68ca593e7638874ffc38c08",
    "value\n0001\n": "22afd8e04572909ae0cafe6bdbdcc4c67db679b6880dcaf4c9f8e4c4dbda1630",
    "sample_id,latitude,pH\nS001,34.052200,7.20\nS002,34.052800,7.18\n": (
        "83e16b933d14f0cc0a2d5718ba2d86b263e129684df8c0becafbc97b26fc13a6"
    ),
}


@pytest.mark.parametrize(("csv_text", "expected"), PUBLISHED_VECTORS.items())
def test_published_vector(csv_text: str, expected: str) -> None:
    """Every published vector still hashes to its documented digest."""
    assert compute_hash(csv_text) == expected
