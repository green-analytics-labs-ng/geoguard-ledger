"""Unit tests for the geochemical plausibility checks."""

import io

import pandas as pd
import pytest
from httpx import AsyncClient

from app.services.anomaly import run_anomaly_detection
from app.services.validation import check_ranges, normalize_parameter_name


def _df(**columns: list[float]) -> pd.DataFrame:
    return pd.DataFrame(columns)


# ── normalize_parameter_name ──────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("pH", "ph"),
        ("PH", "ph"),
        ("dissolved_oxygen", "dissolved_oxygen"),
        ("Dissolved Oxygen", "dissolved_oxygen"),
        ("Dissolved-Oxygen", "dissolved_oxygen"),
        ("Dissolved Oxygen (mg/L)", "dissolved_oxygen"),
        ("Temperature [C]", "temperature"),
        ("  Nitrate  ", "nitrate"),
        ("NO3-N", "no3_n"),
    ],
)
def test_normalize_parameter_name(raw: str, expected: str) -> None:
    assert normalize_parameter_name(raw) == expected


# ── check_ranges ──────────────────────────────────────────────────


def test_in_range_data_produces_no_findings() -> None:
    df = _df(
        pH=[7.1, 7.2, 7.3],
        conductivity=[450.0, 451.0, 452.0],
        temperature=[20.0, 21.0, 22.0],
    )
    assert check_ranges(df) == []


def test_negative_concentration_is_an_error() -> None:
    df = _df(conductivity=[450.0, -118.0, 452.0])
    findings = check_ranges(df)
    assert len(findings) == 1
    assert findings[0].startswith("[ERROR] conductivity:")
    assert "negative" in findings[0]
    assert "(rows 2)" in findings[0]


def test_ph_outside_absolute_range_is_an_error() -> None:
    df = _df(pH=[7.1, 20.5, -3.4])
    findings = check_ranges(df)
    assert len(findings) == 1
    assert findings[0].startswith("[ERROR] pH:")
    assert "0 to 14" in findings[0]
    assert "rows 2, 3" in findings[0]


def test_temperature_outside_plausible_range_is_a_warning() -> None:
    df = _df(temperature=[22.0, 999.99])
    findings = check_ranges(df)
    assert len(findings) == 1
    assert findings[0].startswith("[WARNING] temperature:")
    assert "rows 2" in findings[0]


def test_unknown_columns_are_ignored() -> None:
    df = _df(sample_id=[1.0, 2.0], mystery=[-1.0, -2.0])
    assert check_ranges(df) == []


def test_non_numeric_columns_are_ignored() -> None:
    df = pd.DataFrame({"conductivity": ["not-a-number", "also-bad"]})
    assert check_ranges(df) == []


def test_missing_values_are_ignored() -> None:
    df = pd.DataFrame({"pH": [7.1, None, 7.3]})
    assert check_ranges(df) == []


def test_findings_are_truncated_after_five_rows() -> None:
    df = _df(pH=[-1.0] * 8, conductivity=[450.0] * 8)
    findings = check_ranges(df)
    assert findings[0].startswith("[ERROR] pH:")
    assert findings[0].endswith("rows 1, 2, 3, 4, 5, ...)")


def test_reported_rows_are_one_indexed() -> None:
    """Row numbers must line up with the anomaly report's row flags."""
    df = _df(pH=[7.0, 7.0, -3.0])
    findings = check_ranges(df)
    assert "rows 3" in findings[0]


# ── Integration with the anomaly report ───────────────────────────


def test_anomaly_report_includes_warnings() -> None:
    csv_text = (
        "sample_id,latitude,longitude,pH,conductivity,dissolved_oxygen,temperature\n"
        "S001,34.05,-118.24,7.20,450.00,8.50,22.10\n"
        "S002,34.05,-118.24,7.15,-118.00,8.30,22.30\n"
        "S003,34.05,-118.24,7.18,448.00,8.70,22.00\n"
        "S004,34.05,-118.24,20.50,455.00,8.40,22.20\n"
        "S005,34.05,-118.24,7.19,449.00,8.60,22.40\n"
        "S006,34.05,-118.24,7.25,460.00,8.45,22.15\n"
    )
    result = run_anomaly_detection(csv_text)

    assert "warnings" in result
    assert any("conductivity" in warning for warning in result["warnings"])
    assert any("pH" in warning for warning in result["warnings"])


def test_warnings_are_reported_even_when_scoring_is_skipped() -> None:
    """Range checks are independent of the model, so tiny datasets get them too."""
    csv_text = "sample_id,pH,conductivity\nS001,-1.00,450.00\nS002,25.00,451.00\n"
    result = run_anomaly_detection(csv_text)

    assert result["score"] == 0.0  # too few rows to score
    assert any("pH" in warning for warning in result["warnings"])


def test_clean_dataset_reports_no_warnings() -> None:
    csv_text = (
        "sample_id,latitude,longitude,pH,conductivity,dissolved_oxygen,temperature\n"
        "S001,34.052200,-118.243700,7.20,450.00,8.50,22.10\n"
        "S002,34.052500,-118.244000,7.15,452.00,8.30,22.30\n"
        "S003,34.052800,-118.244300,7.18,448.00,8.70,22.00\n"
        "S004,34.053100,-118.244600,7.22,455.00,8.40,22.20\n"
        "S005,34.053400,-118.244900,7.19,449.00,8.60,22.40\n"
    )
    result = run_anomaly_detection(csv_text)
    assert result["warnings"] == []


def test_validation_can_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.anomaly.settings.geochemical_validation_enabled", False)

    csv_text = "sample_id,pH,conductivity\nS001,-1.00,450.00\nS002,25.00,451.00\nS003,7.10,450.00\n"
    result = run_anomaly_detection(csv_text)
    assert result["warnings"] == []


def test_range_check_does_not_break_on_unparseable_columns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failure inside the advisory checks must not fail the upload."""
    monkeypatch.setattr(
        "app.services.anomaly.check_ranges",
        lambda df: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    csv_text = io.StringIO(
        "sample_id,pH,conductivity\nS001,7.10,450.00\nS002,7.20,451.00\n"
    ).getvalue()
    result = run_anomaly_detection(csv_text)
    assert result["warnings"] == []


# -- API surface ----------------------------------------------------

WARNINGS_CSV = (
    "sample_id,latitude,longitude,pH,conductivity,dissolved_oxygen,temperature\n"
    "S001,34.05,-118.24,7.20,450.00,8.50,22.10\n"
    "S002,34.05,-118.24,7.15,-118.00,8.30,22.30\n"
    "S003,34.05,-118.24,7.18,448.00,8.70,22.00\n"
    "S004,34.05,-118.24,7.22,455.00,8.40,22.20\n"
    "S005,34.05,-118.24,7.19,449.00,8.60,22.40\n"
)


@pytest.mark.asyncio
async def test_create_dataset_response_includes_warnings(
    client: AsyncClient,
    mock_build_transaction,
) -> None:
    """Plausibility findings must reach the API response and be persisted."""
    response = await client.post(
        "/api/v1/datasets",
        files={"file": ("out-of-range.csv", WARNINGS_CSV, "text/csv")},
    )

    assert response.status_code == 201
    body = response.json()
    assert any("conductivity" in warning for warning in body["anomaly_report"]["warnings"])

    detail = await client.get(f"/api/v1/datasets/{body['dataset_id']}")
    stored_warnings = detail.json()["anomaly_report"]["warnings"]
    assert any("conductivity" in warning for warning in stored_warnings)
