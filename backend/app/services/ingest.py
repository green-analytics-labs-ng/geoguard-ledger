"""Upload ingestion: turn any supported file into a hash and analysable text.

Hashing and analysis consume different representations of the same upload:

* **CSV / JSON** are normalized to a canonical CSV string, which is both hashed
  and parsed by the anomaly service. Sharing one representation across both
  formats is what makes a JSON upload hash identically to its CSV equivalent.
* **XML** is canonicalized to deterministic bytes and hashed *as XML* - a CSV
  round-trip would discard element structure and attribute information. The
  canonical text is then flattened for analysis by ``pandas.read_xml``.

Both upload endpoints go through :func:`process_upload` so that hashing is
consistent between submitting a dataset and re-verifying it.
"""

from dataclasses import dataclass

from app.services.hasher import compute_hash, compute_hash_bytes
from app.services.parser import (
    FileFormat,
    canonicalize_xml,
    get_file_format,
    parse_to_csv,
)


@dataclass(frozen=True)
class ProcessedUpload:
    """A validated upload, ready to be hashed and analysed."""

    file_format: FileFormat
    dataset_hash: str
    analysis_text: str


def process_upload(content: bytes, filename: str | None) -> ProcessedUpload:
    """Prepare an uploaded file for hashing and anomaly detection.

    Args:
        content: Raw upload bytes.
        filename: Original filename, used to detect the file format.

    Returns:
        The detected format, the SHA-256 digest of the canonicalized content,
        and the text the anomaly service should analyse.

    Raises:
        ParseError: If the format is unsupported or the content is invalid.
    """
    file_format = get_file_format(filename)

    if file_format == "xml":
        canonical = canonicalize_xml(content)
        return ProcessedUpload(
            file_format="xml",
            dataset_hash=compute_hash_bytes(canonical),
            analysis_text=canonical.decode("utf-8"),
        )

    csv_text = parse_to_csv(content, filename)
    return ProcessedUpload(
        file_format=file_format,
        dataset_hash=compute_hash(csv_text),
        analysis_text=csv_text,
    )
