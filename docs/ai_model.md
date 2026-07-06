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
| `model_version` | string | Version tag (e.g., "isoforest-v1") |
| `summary` | string | Human-readable summary |

### Thresholds

| Range | Badge Color | Interpretation |
|-------|-------------|----------------|
| 0% – 5% | Green | Normal |
| 5% – 20% | Yellow | Suspect — review recommended |
| 20%+ | Red | Anomalous — likely fabrication or instrument error |

### Future: Multi-Model Support

- LSTM autoencoder for temporal geochemical data (time-series well monitoring).
- One-class SVM as an alternative detector.
- Model registry with versioned inference endpoints.
