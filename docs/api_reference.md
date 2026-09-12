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
| `POST` | `/datasets` | Upload and process a CSV, JSON, or XML dataset |
| `POST` | `/datasets/{id}/submit` | Submit a signed transaction to Stellar |
| `GET` | `/datasets` | List all datasets |
| `GET` | `/datasets/{id}` | Get dataset details |
| `POST` | `/batches` | Build a Merkle root over a set of datasets and get an unsigned anchor transaction |
| `POST` | `/batches/{id}/submit` | Submit a signed root transaction and anchor the whole batch |
| `GET` | `/batches` | List batches |
| `GET` | `/batches/{id}` | Get batch details |
| `POST` | `/verify` | Verify a dataset against on-chain proof |

For full request/response schemas, see [SPECIFICATION.md](../SPECIFICATION.md#5-backend-api-specification-fastapi).

## Supported upload formats

`POST /datasets` and the file mode of `POST /verify` accept three formats,
detected from the filename extension (case-insensitive):

| Extension | Hashing | Analysis |
|-----------|---------|----------|
| `.csv` | Canonical CSV (RFC 4180 parsing, UTF-8, normalized line endings, numeric truncation) | Parsed as CSV |
| `.json` | Same canonical CSV as the equivalent CSV upload | Parsed as CSV |
| `.xml` | Canonical XML bytes | Flattened with `pandas.read_xml` |

Uploads that carry the same information produce the same `dataset_hash`
regardless of formatting. CSV and JSON are normalized to one canonical CSV form
(so an integer stays an integer and hashes identically in both). XML is never
converted to CSV before hashing — element structure and attributes are part of
the fingerprint — and is canonicalized as XML: comments and processing
instructions are dropped, attributes are sorted alphabetically, insignificant
whitespace is removed, and no BOM is emitted.

Malformed XML, XML with fewer than two numeric feature columns, and unsupported
extensions (for example `.txt`) are rejected with `400 Bad Request`.

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

## Batch anchoring

Anchoring a Merkle root commits many datasets to a single on-chain entry,
keeping storage cost and rent flat as submissions grow. `POST /batches` returns
the root plus a per-dataset inclusion proof; `POST /batches/{id}/submit` marks
the batch and all of its datasets `anchored` once the signed transaction is
confirmed.

`POST /verify` reports batch membership in an `inclusion` block:

```json
{
  "match": true,
  "on_chain_record": null,
  "local_record": { "dataset_id": "uuid", "status": "anchored" },
  "re_computed_hash": null,
  "inclusion": {
    "root": "64-char-hex",
    "leaf_index": 0,
    "proof": ["64-char-hex"],
    "batch_id": "uuid",
    "verified_locally": true,
    "verified_on_chain": true
  }
}
```

`inclusion` is `null` for datasets anchored individually. `verified_locally`
re-checks the proof in the backend; `verified_on_chain` is the contract's own
`verify_inclusion` verdict, or `null` when it could not be evaluated.

## Maintenance

### `GET /api/v1/maintenance/ttl-status`

Reports how much life the anchored Merkle roots have left. Roots are Persistent
ledger entries, so if renewal stops working they are eventually archived and
verification silently stops answering for every dataset in those batches — this
endpoint is how that shows up as a number instead.

```json
{
  "enabled": true,
  "signer_configured": true,
  "renewal_window_days": 30,
  "root_lifetime_days": 180.0,
  "anchored_roots": 12,
  "roots_without_recorded_expiry": 0,
  "roots_due_for_renewal": 2,
  "roots_past_recorded_expiry": 0,
  "roots_with_renewal_error": 0,
  "next_expiry_at": "2026-10-02T11:15:00+00:00",
  "last_renewed_at": "2026-09-01T03:00:12+00:00"
}
```

Alert on `roots_past_recorded_expiry` above zero, or on
`roots_with_renewal_error` growing: either means the renewal job has stopped
keeping up.

Note that expiry is the deadline **recorded** when a root was anchored or
renewed, derived from the contract's TTL budgets — it is not read back from the
ledger. Treat it as a drift detector: if the contract's budgets change, these
deadlines go stale and say so here rather than failing silently.

Renewal itself is a scheduled command, not an endpoint:

```bash
cd backend
python -m app.jobs.renew_root_ttl --dry-run   # list what would be renewed
python -m app.jobs.renew_root_ttl             # renew for real
```

It exits `0` on a clean run, `1` when any renewal failed (the failure is also
recorded on the batch), and `2` when the job is disabled or has no signing
account configured.
