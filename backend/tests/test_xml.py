"""Tests for XML upload support.

XML is canonicalized into deterministic bytes and hashed as XML, then flattened
for the anomaly pipeline. The property that matters for research integrity is
that two XML files carrying the same information hash identically, no matter how
they were formatted on disk.
"""

from pathlib import Path

import pytest
from httpx import AsyncClient

from app.services.anomaly import run_anomaly_detection
from app.services.ingest import process_upload
from app.services.parser import ParseError, canonicalize_xml

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_XML = (FIXTURES / "sample.xml").read_text(encoding="utf-8")
SAMPLE_XML_BYTES = SAMPLE_XML.encode("utf-8")

TEST_ADDRESS = "GABCDEF123456789012345678901234567890123"

MINIMAL_XML = b"<report><row><a>1</a><b>2</b></row></report>"


# ── Canonicalization ──────────────────────────────────────────────


def test_identical_documents_hash_identically() -> None:
    assert canonicalize_xml(SAMPLE_XML_BYTES) == canonicalize_xml(SAMPLE_XML_BYTES)


def test_hashes_are_stable_across_repeated_calls() -> None:
    hashes = {process_upload(SAMPLE_XML_BYTES, "sample.xml").dataset_hash for _ in range(3)}
    assert len(hashes) == 1


def test_whitespace_and_indentation_do_not_change_the_hash() -> None:
    compact = b"<report><row><a>1</a><b>2</b></row></report>"
    pretty = b"<report>\n    <row>\n        <a>1</a>\n        <b>2</b>\n    </row>\n</report>\n"

    assert canonicalize_xml(compact) == canonicalize_xml(pretty)


def test_attribute_order_does_not_change_the_hash() -> None:
    first = b'<row id="S1" lat="34.0" lon="-118.0"/>'
    second = b'<row lon="-118.0" lat="34.0" id="S1"/>'

    assert canonicalize_xml(first) == canonicalize_xml(second)


def test_comments_and_processing_instructions_are_ignored() -> None:
    plain = b"<report><row><a>1</a></row></report>"
    annotated = (
        b"<?xml version='1.0' encoding='UTF-8'?>\n"
        b"<!-- exported by LIMS v3 -->\n"
        b"<report><!-- inline note --><row><a>1</a></row><?pi target?></report>"
    )

    assert canonicalize_xml(plain) == canonicalize_xml(annotated)


def test_a_utf8_bom_is_stripped() -> None:
    with_bom = b"\xef\xbb\xbf" + MINIMAL_XML
    assert canonicalize_xml(with_bom) == canonicalize_xml(MINIMAL_XML)


def test_changing_a_value_changes_the_hash() -> None:
    original = b"<report><row><a>1</a></row></report>"
    altered = b"<report><row><a>2</a></row></report>"

    assert canonicalize_xml(original) != canonicalize_xml(altered)


def test_attribute_and_element_text_whitespace_is_preserved() -> None:
    """Only whitespace-only nodes are dropped; data text is kept verbatim."""
    canonical = canonicalize_xml(b'<row note="  keep me  "><a> x </a></row>')
    assert b"  keep me  " in canonical
    assert b" x " in canonical


def test_empty_elements_use_the_short_form() -> None:
    assert canonicalize_xml(b"<row><blank></blank></row>") == b"<row><blank /></row>"


def test_output_has_no_xml_declaration() -> None:
    assert not canonicalize_xml(MINIMAL_XML).startswith(b"<?xml")


def test_malformed_xml_raises_parse_error() -> None:
    with pytest.raises(ParseError, match="Malformed XML"):
        canonicalize_xml(b"<report><row></report>")


def test_non_utf8_xml_raises_parse_error() -> None:
    with pytest.raises(ParseError, match="UTF-8"):
        canonicalize_xml(b"\xff\xfe\x00\x01")


def test_empty_xml_raises_parse_error() -> None:
    with pytest.raises(ParseError):
        canonicalize_xml(b"")


# ── process_upload ────────────────────────────────────────────────


def test_process_upload_detects_xml() -> None:
    processed = process_upload(SAMPLE_XML_BYTES, "sample.xml")

    assert processed.file_format == "xml"
    assert len(processed.dataset_hash) == 64
    assert processed.analysis_text.startswith("<GeochemistryReport")


def test_process_upload_hashes_xml_as_xml() -> None:
    """The digest is over canonical XML, not a CSV rendering of it."""
    processed = process_upload(SAMPLE_XML_BYTES, "sample.xml")

    assert processed.dataset_hash != process_upload(b"a,b\n1,2\n", "data.csv").dataset_hash


# ── Anomaly detection on XML ──────────────────────────────────────


def test_anomaly_detection_runs_on_flattened_xml() -> None:
    processed = process_upload(SAMPLE_XML_BYTES, "sample.xml")
    result = run_anomaly_detection(processed.analysis_text, "xml")

    assert result["model_version"] == "isoforest_v1"
    assert 0.0 <= result["score"] <= 1.0
    assert isinstance(result["flags"], list)
    assert result["warnings"] == []


def test_anomaly_detection_reports_range_warnings_for_impossible_xml() -> None:
    xml = (
        b"<report>"
        b'<row id="S1" latitude="34.0" longitude="-118.0">'
        b"<pH>-1.5</pH><conductivity>450</conductivity>"
        b"<dissolved_oxygen>8.5</dissolved_oxygen><temperature>22</temperature></row>"
        b'<row id="S2" latitude="34.0" longitude="-118.0">'
        b"<pH>7.2</pH><conductivity>451</conductivity>"
        b"<dissolved_oxygen>8.4</dissolved_oxygen><temperature>22</temperature></row>"
        b"</report>"
    )
    processed = process_upload(xml, "impossible.xml")
    result = run_anomaly_detection(processed.analysis_text, "xml")

    assert any("pH" in warning for warning in result["warnings"])


# ── API ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_dataset_accepts_xml(
    client: AsyncClient,
    mock_build_transaction,
) -> None:
    response = await client.post(
        "/api/v1/datasets",
        files={"file": ("sample.xml", SAMPLE_XML, "application/xml")},
    )

    assert response.status_code == 201
    body = response.json()
    assert len(body["dataset_hash"]) == 64
    assert body["anomaly_report"]["model_version"] == "isoforest_v1"


@pytest.mark.asyncio
async def test_create_dataset_accepts_xml_without_a_declaration(
    client: AsyncClient,
    mock_build_transaction,
) -> None:
    response = await client.post(
        "/api/v1/datasets",
        files={"file": ("mini.xml", MINIMAL_XML, "application/xml")},
    )

    assert response.status_code == 201


@pytest.mark.asyncio
async def test_create_dataset_rejects_malformed_xml(
    client: AsyncClient,
) -> None:
    """Malformed XML must be a 400 with a clear message, never a 500."""
    response = await client.post(
        "/api/v1/datasets",
        files={"file": ("broken.xml", b"<report><row></report>", "application/xml")},
    )

    assert response.status_code == 400
    assert "Malformed XML" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_dataset_rejects_xml_without_numeric_columns(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/datasets",
        files={
            "file": (
                "text-only.xml",
                b"<report><row><a>x</a><b>y</b></row></report>",
                "application/xml",
            ),
        },
    )

    assert response.status_code == 400
    assert "numeric" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_dataset_still_rejects_unsupported_formats(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/datasets",
        files={"file": ("data.txt", b"not data", "text/plain")},
    )

    assert response.status_code == 400
    assert "csv" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_csv_upload_is_unaffected(
    client: AsyncClient,
    mock_build_transaction,
) -> None:
    csv_content = (
        "sample_id,latitude,longitude,pH,conductivity,dissolved_oxygen,temperature\n"
        "S001,34.052200,-118.243700,7.20,450.00,8.50,22.10\n"
        "S002,34.052500,-118.244000,7.15,452.00,8.30,22.30\n"
        "S003,34.052800,-118.244300,7.18,448.00,8.70,22.00\n"
        "S004,34.053100,-118.244600,7.22,455.00,8.40,22.20\n"
        "S005,34.053400,-118.244900,7.19,449.00,8.60,22.40\n"
    )
    response = await client.post(
        "/api/v1/datasets",
        files={"file": ("sample.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 201
    assert response.json()["anomaly_report"]["score"] is not None


@pytest.mark.asyncio
async def test_verify_recomputes_the_same_xml_hash(
    client: AsyncClient,
    mock_build_transaction,
    mock_verify_on_chain_not_found,
) -> None:
    """A verifier re-uploading the XML must reproduce the anchored hash."""
    created = await client.post(
        "/api/v1/datasets",
        files={"file": ("sample.xml", SAMPLE_XML, "application/xml")},
    )
    dataset_hash = created.json()["dataset_hash"]

    verified = await client.post(
        "/api/v1/verify",
        files={"file": ("sample.xml", SAMPLE_XML, "application/xml")},
    )

    assert verified.status_code == 200
    assert verified.json()["re_computed_hash"] == dataset_hash


@pytest.mark.asyncio
async def test_verify_rejects_malformed_xml(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/verify",
        files={"file": ("broken.xml", b"<report>", "application/xml")},
    )

    assert response.status_code == 400
