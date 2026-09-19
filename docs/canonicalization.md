# CSV Canonicalization v1

Every `dataset_hash` is computed over a canonical form of the upload, so any
third party can re-hash the same data and reproduce the exact fingerprint. This
is the normative description of that form.

The rule set is versioned as `CANONICALIZATION_VERSION` (currently `1`) and the
version is returned alongside every hash, because changing any rule re-hashes
every dataset and an on-chain anchor made under an older rule set can no longer
be reproduced by the current code.

## Rules

CSV and JSON uploads are both normalized to this canonical CSV form. XML is
canonicalized separately, as XML, and is not covered here.

1. Parse as RFC 4180 CSV and decode as UTF-8; a leading BOM is dropped.
2. Normalize line endings to `\n`.
3. Normalize every cell to Unicode NFC.
4. Strip leading and trailing whitespace from every cell.
5. Render numeric cells as one canonical decimal form. A cell that is an
   integer, a decimal, or scientific notation is parsed exactly and rounded
   **half-even to 6 decimal places**, then written in plain (non-exponent)
   notation with exactly 6 fractional digits. A numeric-looking cell with a
   leading zero (`0001`) is treated as an identifier and left untouched.
6. Preserve row order exactly as it appears in the file. Rows are never sorted
   or reordered.
7. Re-serialize with RFC 4180 quoting and `\n` line endings.

The SHA-256 digest is then taken over the UTF-8 bytes of that canonical CSV
string.

## Test vectors

`\n` denotes a newline. Rows that share a digest are deliberately equivalent
under the rules above.

| Input | Expected SHA-256 |
|-------|------------------|
| `value\n5\n` (integer) | `fa0f3c48a79985ff55647a782576d90c88d5708cccef42f0510f007ce9eab972` |
| `value\n5.0\n` (decimal, same number) | `fa0f3c48a79985ff55647a782576d90c88d5708cccef42f0510f007ce9eab972` |
| `\ufeffvalue\r\n 5 \r\n` (BOM, CRLF, padding, same number) | `fa0f3c48a79985ff55647a782576d90c88d5708cccef42f0510f007ce9eab972` |
| `value\n1e-3\n` (scientific notation) | `c3ac2598c41e864d5c6e708bfaebdbd10ab8a6359aa04c95395e9be2ff6a0ad8` |
| `value\n0.001\n` (same number) | `c3ac2598c41e864d5c6e708bfaebdbd10ab8a6359aa04c95395e9be2ff6a0ad8` |
| `value\n7.1234567\n` (rounds to 6 d.p.) | `ca2ca79fec9672254626538d657f475c8db16b9a6ffa7d3afdce7a3311be7020` |
| `value\né\n` (NFC `U+00E9`) | `623953c55233048064eec0e74cfa54bf9bda8eb1c68ca593e7638874ffc38c08` |
| `value\ne\u0301\n` (NFD `e` + combining acute, same text) | `623953c55233048064eec0e74cfa54bf9bda8eb1c68ca593e7638874ffc38c08` |
| `value\n0001\n` (identifier, not the number 1) | `22afd8e04572909ae0cafe6bdbdcc4c67db679b6880dcaf4c9f8e4c4dbda1630` |
| `sample_id,latitude,pH\nS001,34.052200,7.20\nS002,34.052800,7.18\n` | `83e16b933d14f0cc0a2d5718ba2d86b263e129684df8c0becafbc97b26fc13a6` |

Row order is significant: `value\n1\n2\n` and `value\n2\n1\n` hash differently.

These vectors are asserted by `backend/tests/test_hasher.py`. If a rule changes,
bump `CANONICALIZATION_VERSION` and regenerate the table — an unchanged version
with changed digests means anchored hashes can no longer be reproduced.
