# AI Anomaly Detection Approach

## Model: Isolation Forest

### Why Isolation Forest?

Geochemical datasets are high-dimensional and typically have no labeled anomalies. Isolation Forest:

- Is **unsupervised** — no labeled data required.
- Handles **high-dimensional** data well.
- Provides **per-row anomaly scores** (0.0–1.0).
- Is **lightweight** — runs synchronously in the API.

### Input Features

The model analyzes all numeric columns in the uploaded CSV. Typical geochemical features include:

- pH
- Conductivity (µS/cm)
- Dissolved oxygen (mg/L)
- Temperature (°C)
- Ion concentrations (Na⁺, K⁺, Ca²⁺, Mg²⁺, Cl⁻, SO₄²⁻, HCO₃⁻)

### Output

| Field | Type | Description |
|-------|------|-------------|
| `score` | float (0.0–1.0) | Overall anomaly probability for the dataset |
| `flags` | int[] | Row indices flagged as anomalous |
| `model_version` | string | Version tag (e.g., "isoforest_v1") |
| `summary` | string | Human-readable summary |

### Thresholds

| Range | Badge Color | Interpretation |
|-------|-------------|----------------|
| 0% – 5% | Green | Normal |
| 5% – 20% | Yellow | Suspect — review recommended |
| 20%+ | Red | Anomalous — likely fabrication or instrument error |

### Geochemical Range Validation

The statistical model is fitted **per dataset**, so it can only flag rows that
deviate from that dataset's own distribution. It is therefore blind to
*systematic* errors: a dataset whose pH column is uniformly `3.0` is perfectly
self-consistent and scores 0%, yet is impossible for drinking water.

To cover that gap, every upload is also checked against coarse,
domain-informed plausibility bounds before the anomaly report is returned.
Findings appear in the report's `warnings` array; they never block an upload.

| Parameter | Plausible range | Severity |
|-----------|-----------------|----------|
| `pH` | 0 – 14 | Error |
| `temperature` | −10 – 50 °C | Warning |
| `dissolved_oxygen` | 0 – 20 mg/L | Warning |
| `turbidity` | 0 – 4000 NTU | Warning |
| `salinity` | 0 – 400 PSU | Warning |
| All measured concentrations | ≥ 0 | Error (negative is impossible) |

Column names are matched case-insensitively after normalising punctuation and
dropping bracketed units, so `pH`, `PH` and `Dissolved Oxygen (mg/L)` are all
recognised. Concentrations include the common ions (`Na`, `K`, `Ca`, `Mg`,
`Cl`, `SO₄`, `NO₃`, `F`, metals such as `Pb`/`As`/`Fe`, and aggregate measures
like `TDS`, `hardness`, `turbidity` and `conductivity`).

Each finding is prefixed `[ERROR]` for physically impossible values or
`[WARNING]` for values that are implausible but not impossible, and lists the
1-indexed rows involved (truncated after five rows):

```text
[ERROR] pH: 1 value(s) outside the plausible range 0 to 14 (rows 4)
[ERROR] conductivity: 1 value(s) negative value(s); a measured concentration cannot be negative (rows 3)
```

Row numbers line up with the `flags` array, so a warning and a flagged row can
be cross-referenced.

Set `GEOCHEMICAL_VALIDATION_ENABLED=false` to disable these checks. Ranges live
in `backend/app/services/validation.py`.

### Future: Multi-Model Support

- LSTM autoencoder for temporal geochemical data (time-series well monitoring).
- One-class SVM as an alternative detector.
- Model registry with versioned inference endpoints.
