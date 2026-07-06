# GeoGuard Ledger API Reference

Full API reference is available via OpenAPI at `/docs` when the backend is running.

## Base URL

```
http://localhost:8000/api/v1
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/datasets` | Upload and process a CSV dataset |
| `POST` | `/datasets/{id}/submit` | Submit a signed transaction to Stellar |
| `GET` | `/datasets` | List all datasets |
| `GET` | `/datasets/{id}` | Get dataset details |
| `POST` | `/verify` | Verify a dataset against on-chain proof |

For full request/response schemas, see [SPECIFICATION.md](../SPECIFICATION.md#5-backend-api-specification-fastapi).
