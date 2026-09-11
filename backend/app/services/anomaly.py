"""AI anomaly detection service.

Uses Isolation Forest to detect anomalous rows in geochemical data.
The model is fit **per-dataset** on the numeric columns of the uploaded data,
making it unsupervised and adaptive to whatever features are present.

Rows are flagged using the **IQR method** on the raw decision-function scores,
a statistically robust approach that avoids false positives on small datasets.
The overall dataset score reflects the fraction of flagged rows.

Model versioning:
  isoforest_v1 — IsolationForest with per-dataset fitting and IQR flagging
"""

import io
import logging
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from app.config import settings
from app.core.exceptions import AnomalyDetectionError
from app.services.parser import FileFormat
from app.services.validation import check_ranges

logger = logging.getLogger(__name__)

# Minimum rows required to run anomaly detection.
# For rows < MIN_ROWS the dataset score is always 0.0 (too small to infer).
_MIN_ROWS = 5

# Z-score multiplier for the IQR lower fence.
# Standard Tukey's fences: 1.5 for "outlier", 3.0 for "far out".
_IQR_MULTIPLIER = 1.5

_ID_COLUMNS = frozenset(
    {
        "sample_id",
        "sampleid",
        "sample id",
        "id",
        "site_id",
        "siteid",
        "station_id",
        "stationid",
        "well_id",
        "wellid",
    }
)

_COORD_COLUMNS = frozenset(
    {
        "lat",
        "latitude",
        "long",
        "longitude",
        "lon",
        "lng",
    }
)


def _read_source(source_text: str, file_format: FileFormat) -> pd.DataFrame:
    """Parse the analysable text into a DataFrame.

    CSV and JSON both arrive as canonical CSV. XML is flattened with
    ``pandas.read_xml``, whose default ``xpath`` maps each repeating child
    element to a row and its attributes plus child elements to columns.

    Raises:
        AnomalyDetectionError: If the content cannot be parsed.
    """
    try:
        if file_format == "xml":
            return pd.read_xml(io.StringIO(source_text), parser="etree")
        return pd.read_csv(io.StringIO(source_text))
    except Exception as exc:
        raise AnomalyDetectionError(
            f"Failed to parse {file_format.upper()}: {exc}", status_code=400
        ) from exc


def _extract_features(df: pd.DataFrame) -> pd.DataFrame:
    """Return a DataFrame of numeric feature columns suitable for anomaly detection.

    Drops non-numeric columns, known ID columns, and coordinate columns.
    Raises ``AnomalyDetectionError`` if fewer than 2 numeric columns remain.
    """
    numeric = df.select_dtypes(include=[np.number])

    drop_cols = set()
    for col in numeric.columns:
        lower = col.lower().strip()
        if lower in _ID_COLUMNS or lower in _COORD_COLUMNS:
            drop_cols.add(col)

    features = numeric.drop(columns=list(drop_cols), errors="ignore")

    if features.shape[1] < 2:
        raise AnomalyDetectionError(
            "Dataset must contain at least 2 numeric feature columns "
            "(latitude/longitude alone is insufficient)",
            status_code=400,
        )

    features = features.dropna()
    if features.empty:
        raise AnomalyDetectionError(
            "All rows have missing values in the numeric feature columns",
            status_code=400,
        )

    return features


def _flag_via_iqr(scores: np.ndarray, multiplier: float = _IQR_MULTIPLIER) -> np.ndarray:  # type: ignore[type-arg]
    """Return a boolean mask flagging scores below the IQR lower fence.

    The IQR (Tukey) method is robust to the score distribution — it only
    flags values that are extreme relative to the dataset's own spread.
    This avoids flagging any rows when all scores are tightly clustered.
    """
    q1 = float(np.percentile(scores, 25))
    q3 = float(np.percentile(scores, 75))
    iqr = q3 - q1

    if iqr < 1e-12:
        return np.zeros_like(scores, dtype=bool)

    lower_fence = q1 - multiplier * iqr
    return scores < lower_fence


def _range_warnings(df: pd.DataFrame) -> list[str]:
    """Run the geochemical plausibility checks, never failing the upload.

    These checks are advisory metadata, so any unexpected failure degrades to
    "no warnings" rather than rejecting an otherwise valid dataset.
    """
    if not settings.geochemical_validation_enabled:
        return []

    try:
        return check_ranges(df)
    except Exception as exc:  # noqa: BLE001 - must not break ingestion
        logger.warning("Geochemical range validation failed: %s", exc)
        return []


def _build_summary(dataset_score: float, n_rows: int, n_flagged: int) -> str:
    """Produce a human-readable summary string (no emoji, ASCII-safe)."""
    pct = (n_flagged / n_rows * 100) if n_rows else 0.0
    threshold = settings.ai_anomaly_threshold

    if dataset_score < 0.05:
        label = "NORMAL"
    elif dataset_score < threshold:
        label = "SUSPECT"
    else:
        label = "ANOMALOUS"

    return (
        f"[{label}] Score={dataset_score:.1%}, "
        f"{n_flagged}/{n_rows} rows flagged ({pct:.1f}%)."
        + (" Review recommended." if dataset_score >= 0.05 and dataset_score < threshold else "")
        + (" Likely fabrication or instrument error." if dataset_score >= threshold else "")
    )


# ── Public API ────────────────────────────────────────────────────


def run_anomaly_detection(
    source_text: str,
    file_format: FileFormat = "csv",
) -> dict[str, Any]:
    """Run anomaly detection on a dataset.

    Fits an Isolation Forest on the numeric columns of the dataset (per-call),
    scores each row, and uses the IQR method to flag anomalous rows.

    Args:
        source_text: The dataset as canonical CSV, or canonical XML.
        file_format: ``"csv"``, ``"json"`` or ``"xml"``. CSV and JSON are both
            parsed as CSV because they share a canonical representation.

    Returns:
        dict with keys:
            - score (float): Fraction of rows flagged as anomalous (0.0–1.0).
            - flags (list[int]): 1-indexed row indices flagged as anomalous.
            - model_version (str): Version tag (``ai_model_version`` from config).
            - summary (str): Human-readable one-line description.
            - warnings (list[str]): Geochemical plausibility findings, which are
              independent of the statistical model and therefore also reported
              for datasets too small to score.

    Raises:
        AnomalyDetectionError: If the CSV is empty, has too few numeric
            columns, or cannot be parsed.
    """
    raw_df = _read_source(source_text, file_format)

    if raw_df.empty:
        raise AnomalyDetectionError("Dataset is empty", status_code=400)

    # Domain checks run against the raw columns, independently of the model.
    warnings = _range_warnings(raw_df)

    features = _extract_features(raw_df)
    n_rows = len(features)
    n_features = features.shape[1]

    # Datasets smaller than MIN_ROWS are too small for meaningful inference.
    if n_rows < _MIN_ROWS:
        logger.info(
            "Dataset too small (%d rows, minimum %d) for anomaly detection",
            n_rows,
            _MIN_ROWS,
        )
        return {
            "score": 0.0,
            "flags": [],
            "model_version": settings.ai_model_version,
            "summary": (
                f"[SKIPPED] Dataset has only {n_rows} rows"
                f" (< {_MIN_ROWS} minimum). No anomaly detection performed."
            ),
            "warnings": warnings,
        }

    # Fit Isolation Forest on this dataset's features.
    # contamination=0.5 sets the decision_function offset to the median
    # of the path-length scores, centering the raw scores around zero.
    # We do NOT rely on the built-in predict() threshold — instead we
    # apply our own IQR-based flagging on the raw scores, which is
    # robust to the score distribution regardless of dataset size.
    model = IsolationForest(
        n_estimators=100,
        contamination=0.5,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(features.values)

    # Score each row. decision_function: higher = normal, lower = anomalous.
    raw_scores: np.ndarray = model.decision_function(features.values)  # type: ignore[type-arg]

    # Flag row indices using the IQR method
    flagged_mask = _flag_via_iqr(raw_scores)
    n_flagged = int(flagged_mask.sum())

    # Dataset score = fraction of rows flagged
    dataset_score = round(n_flagged / n_rows, 4)

    # Map flagged mask back to 1-indexed positions in the *original* CSV
    flag_indices_original = raw_df.index[flagged_mask].tolist()
    flags = [int(i + 1) for i in flag_indices_original]

    summary = _build_summary(dataset_score, n_rows, n_flagged)

    logger.info(
        "Anomaly detection: score=%.4f, flagged=%d/%d, features=%d",
        dataset_score,
        n_flagged,
        n_rows,
        n_features,
    )

    return {
        "score": dataset_score,
        "flags": flags,
        "model_version": settings.ai_model_version,
        "summary": summary,
        "warnings": warnings,
    }
