"""Geochemical plausibility checks for uploaded datasets.

The Isolation Forest model is statistical: it flags rows that deviate from a
dataset's *own* distribution. That makes it blind to systematic errors, where
every value is shifted in the same direction - a dataset whose pH column is
uniformly 3.0 looks perfectly self-consistent, yet is impossible for drinking
water. These checks fill that gap with coarse, domain-informed bounds.

They are deliberately conservative: they flag values that are impossible or
highly implausible for environmental water/soil samples, not values that are
merely unusual. Findings never block an upload - they are returned alongside
the statistical anomaly result for the researcher to review.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

import pandas as pd

Severity = Literal["warning", "error"]

# Rows listed in a message before it is truncated with an ellipsis.
_MAX_ROWS_PER_FINDING = 5

# Parameters where *any* negative value is physically impossible, because the
# quantity is a measured concentration or count. Keyed by normalised column
# name (see ``_normalize``).
_NON_NEGATIVE_PARAMETERS: frozenset[str] = frozenset(
    {
        "alkalinity",
        "aluminum",
        "aluminium",
        "ammonia",
        "ammonium",
        "arsenic",
        "barium",
        "bod",
        "boron",
        "bromide",
        "cadmium",
        "calcium",
        "chloride",
        "chromium",
        "cl",
        "cod",
        "coliform",
        "color",
        "colour",
        "conductivity",
        "copper",
        "depth",
        "doc",
        "e_coli",
        "ec",
        "f",
        "fe",
        "fluoride",
        "hardness",
        "hg",
        "iron",
        "lead",
        "magnesium",
        "manganese",
        "mercury",
        "nickel",
        "nitrate",
        "nitrite",
        "no2",
        "no3",
        "nh4",
        "organic_carbon",
        "phosphate",
        "phosphorus",
        "potassium",
        "po4",
        "salinity",
        "selenium",
        "se",
        "silica",
        "sio2",
        "sodium",
        "so4",
        "specific_conductance",
        "sulfate",
        "sulphate",
        "tds",
        "toc",
        "total_coliform",
        "total_dissolved_solids",
        "total_hardness",
        "total_phosphorus",
        "tss",
        "turbidity",
        "zinc",
        "zn",
    }
)


@dataclass(frozen=True)
class ParameterBounds:
    """Plausible range for a named geochemical parameter."""

    minimum: float | None
    maximum: float | None
    severity: Severity
    unit: str = ""


# Parameters with a meaningful upper and/or lower bound. ``None`` means
# unbounded in that direction.
_PARAMETER_BOUNDS: dict[str, ParameterBounds] = {
    # pH is bounded by chemistry rather than by site, so 0-14 is absolute.
    "ph": ParameterBounds(0.0, 14.0, "error"),
    # Surface-water temperature: geothermal and polar sites are genuinely
    # extreme, so out-of-range is advisory.
    "temperature": ParameterBounds(-10.0, 50.0, "warning", "C"),
    "temp": ParameterBounds(-10.0, 50.0, "warning", "C"),
    # Dissolved oxygen cannot exceed atmospheric saturation by a wide margin.
    "dissolved_oxygen": ParameterBounds(0.0, 20.0, "warning", "mg/L"),
    "do": ParameterBounds(0.0, 20.0, "warning", "mg/L"),
    "turbidity": ParameterBounds(0.0, 4000.0, "warning", "NTU"),
    "salinity": ParameterBounds(0.0, 400.0, "warning", "PSU"),
}


def normalize_parameter_name(name: str) -> str:
    """Normalise a column header to a lookup key.

    Drops bracketed unit suffixes and collapses punctuation/whitespace, so
    ``"Dissolved Oxygen (mg/L)"``, ``"dissolved_oxygen"`` and
    ``"Dissolved-Oxygen"`` all resolve to ``"dissolved_oxygen"``.
    """
    without_units = re.sub(r"[([].*?[)\]]", " ", name)
    return re.sub(r"[^a-z0-9]+", "_", without_units.strip().lower()).strip("_")


def check_ranges(df: pd.DataFrame) -> list[str]:
    """Return human-readable range findings for a dataset's columns.

    Args:
        df: The parsed dataset, with one column per measured parameter.

    Returns:
        One string per violating column, prefixed with ``[ERROR]`` or
        ``[WARNING]``. Empty when no column is recognisable or in range.
    """
    # Row positions are reported relative to the data, so normalise the index.
    df = df.reset_index(drop=True)

    findings: list[str] = []

    for column in df.columns:
        parameter = normalize_parameter_name(str(column))
        bounds = _PARAMETER_BOUNDS.get(parameter)
        is_non_negative = parameter in _NON_NEGATIVE_PARAMETERS

        if bounds is None and not is_non_negative:
            continue

        values = pd.to_numeric(df[column], errors="coerce").dropna()
        if values.empty:
            continue

        # Impossible values are reported as errors and take precedence over
        # the advisory range check for the same column.
        if is_non_negative:
            negatives = values[values < 0]
            if not negatives.empty:
                findings.append(
                    _format_finding(
                        column=str(column),
                        severity="error",
                        positions=negatives.index.tolist(),
                        reason="negative value(s); a measured concentration cannot be negative",
                    )
                )

        if bounds is not None:
            out_of_range = _outside(values, bounds.minimum, bounds.maximum)
            if not out_of_range.empty:
                findings.append(
                    _format_finding(
                        column=str(column),
                        severity=bounds.severity,
                        positions=out_of_range.index.tolist(),
                        reason=f"outside the plausible range {_describe_bounds(bounds)}",
                    )
                )

    return findings


def _outside(values: pd.Series, minimum: float | None, maximum: float | None) -> pd.Series:
    """Return the subset of ``values`` that violates the inclusive bounds."""
    mask = pd.Series(False, index=values.index)
    if minimum is not None:
        mask |= values < minimum
    if maximum is not None:
        mask |= values > maximum
    return values[mask]


def _describe_bounds(bounds: ParameterBounds) -> str:
    """Render bounds as a readable range, e.g. ``0 to 14``."""
    lower = "-inf" if bounds.minimum is None else f"{bounds.minimum:g}"
    upper = "inf" if bounds.maximum is None else f"{bounds.maximum:g}"
    unit = f" {bounds.unit}" if bounds.unit else ""
    return f"{lower} to {upper}{unit}"


def _format_finding(
    *,
    column: str,
    severity: Severity,
    positions: list[int],
    reason: str,
) -> str:
    """Build a single finding string with a truncated list of row numbers."""
    rows = [str(position + 1) for position in positions[:_MAX_ROWS_PER_FINDING]]
    if len(positions) > _MAX_ROWS_PER_FINDING:
        rows.append("...")

    label = "ERROR" if severity == "error" else "WARNING"
    return f"[{label}] {column}: {len(positions)} value(s) {reason} (rows {', '.join(rows)})"
