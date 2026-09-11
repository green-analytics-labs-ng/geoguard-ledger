# GeoGuard Ledger API Reference

Full API reference is available via OpenAPI at `/docs` when the backend is running.

## Base URL

```
http://localhost:8000/api/v1
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check (probes Soroban RPC connectivity) |
| `POST` | `/datasets` | Upload and process a CSV or JSON dataset |
| `POST` | `/datasets/{id}/submit` | Submit a signed transaction to Stellar |
| `GET` | `/datasets` | List all datasets |
| `GET` | `/datasets/{id}` | Get dataset details |
| `POST` | `/verify` | Verify a dataset against on-chain proof |

For full request/response schemas, see [SPECIFICATION.md](../SPECIFICATION.md#5-backend-api-specification-fastapi).

## Health check

`GET /health` probes the configured Soroban RPC endpoint on every request
rather than assuming connectivity:

```json
{
  "status": "ok",
  "soroban_rpc": "connected"
}
```

`soroban_rpc` is `"unreachable"` when the RPC node times out, errors, or
reports an unhealthy status. The probe timeout is configurable via
`SOROBAN_RPC_HEALTH_TIMEOUT_SECONDS` (default 3s). `status` describes the API
itself, so it remains `"ok"` while a dependency is down.

## Upload limits

Uploads are capped at `MAX_UPLOAD_SIZE_BYTES` (default 50 MB, matching the
frontend limit). The check runs server-side before the request body is read, so
it cannot be bypassed by calling the API directly. Oversized uploads receive
`413 Payload Too Large`:

```json
{ "detail": "File too large - maximum upload size is 50 MB" }
```

## Anomaly report warnings

Alongside the statistical score, the anomaly report carries domain-informed
plausibility warnings. They are independent of the model, so they are reported
even for datasets too small to score, and are persisted with the dataset:

```json
{
  "score": 0.0,
  "flags": [],
  "model_version": "isoforest_v1",
  "summary": "[NORMAL] Score=0.0%, 0/6 rows flagged (0.0%).",
  "warnings": [
    "[ERROR] pH: 1 value(s) outside the plausible range 0 to 14 (rows 4)"
  ]
}
```

See [ai_model.md](ai_model.md#geochemical-range-validation) for the full set of
checked parameters.
