# GeoGuard Ledger API Reference

Full API reference is available via OpenAPI at `/docs` when the backend is running.

## Base URL

```
http://localhost:8000/api/v1
```

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | Public | Health check (probes Soroban RPC connectivity) |
| `POST` | `/datasets` | API key | Analyze an upload: canonicalize, hash, and score it. No wallet required |
| `POST` | `/datasets/{id}/anchor` | API key | Bind the researcher's address and build the unsigned anchor transaction |
| `POST` | `/datasets/{id}/submit` | API key | Submit a signed transaction to Stellar |
| `GET` | `/datasets` | Public | List all datasets |
| `GET` | `/datasets/{id}` | Public | Get dataset details |
| `POST` | `/batches` | API key | Build a Merkle root over a set of datasets and get an unsigned anchor transaction |
| `POST` | `/batches/{id}/submit` | API key | Submit a signed root transaction and anchor the whole batch |
| `GET` | `/batches` | Public | List batches |
| `GET` | `/batches/{id}` | Public | Get batch details |
| `POST` | `/verify` | Public | Verify a dataset against on-chain proof |

For full request/response schemas, see [SPECIFICATION.md](../SPECIFICATION.md#5-backend-api-specification-fastapi).

## Authentication

Every endpoint that uploads or anchors requires an `X-API-Key` header. Read
endpoints, `POST /verify`, and `GET /health` are public: permissionless
verification is a feature, and a prober that cannot reach `/health` is not a
useful prober.

```bash
curl -X POST http://localhost:8000/api/v1/datasets \
  -H "X-API-Key: $GEOGUARD_API_KEY" \
  -F "file=@measurements.csv"
```

The key comes from the comma-separated `API_KEYS` environment variable. With
`API_KEYS` empty the app **refuses to start** unless
`ALLOW_UNAUTHENTICATED_WRITES=true` is set alongside it, so an open write API is
an explicit development choice rather than a default a checkout can drift into.
That opt-in is honoured in development only — outside development a key is
always required — and setting it logs a warning at boot. Multiple keys are
supported so a key can be rotated without downtime: add the new one alongside
the old, deploy, then remove the old one.

Comparison against the configured keys is constant-time, and every key is
compared even after a match, so neither a wrong key nor a right one is
distinguishable by response timing.

Failures return `401 Unauthorized` and never reach the endpoint:

```json
{ "detail": "Missing X-API-Key header" }
```

```json
{ "detail": "Invalid API key" }
```

In the frontend the key is entered on the **Settings** page, stored in the
browser's `localStorage`, and attached by the API client to the protected write
endpoints (uploads and anchoring) only. `POST /verify` stays public and never
carries the key, so the shared secret is not sent on permissionless calls.

## Rate limits

The upload and verification endpoints parse and hash a file, and verification
also queries the Soroban RPC, so they are counted per client IP over a sliding
window:

| Setting | Default | Meaning |
|---------|:------:|---------|
| `RATE_LIMIT_ENABLED` | `true` | Master switch for the limiter |
| `RATE_LIMIT_REQUESTS` | `30` | Requests allowed per window, per endpoint |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Length of the sliding window |

Each endpoint has its own allowance, so an upload does not consume the
verification budget. Exceeding the limit returns `429 Too Many Requests` with a
`Retry-After` header naming the window:

```json
{ "detail": "Rate limit exceeded - at most 30 requests per 60 seconds" }
```

Behind a reverse proxy the client is read from `X-Forwarded-For`, but only when
the connecting peer is listed in `TRUSTED_PROXIES` — a JSON array of addresses
or CIDRs, empty by default. Without it the header is ignored, so every caller
behind the proxy shares one window; with it, each forwarded client gets its own,
and hops that are themselves trusted proxies are skipped to find the real
client. A malformed entry fails at boot rather than silently reverting to the
proxy's address.

The counters live in the API process, so this bounds a single abusive client
rather than acting as a shared quota across workers. A distributed store (for
example Redis) is the natural replacement if the deployment ever runs multiple
replicas.

## Analyzing and anchoring are separate steps

Uploading no longer involves a wallet. `POST /datasets` canonicalizes the
upload, computes its SHA-256 hash, runs anomaly detection, and stores the
dataset as `analyzed` — no submitter, and no transaction, because nothing has
been committed to the network yet:

```json
{
  "dataset_id": "3f1a...",
  "dataset_hash": "9c2b...",
  "anomaly_report": { "score": 0.1667, "flags": [6], "model_version": "isoforest_v1", "summary": "..." },
  "created_at": "2026-09-17T09:00:00Z"
}
```

The address is bound by `POST /datasets/{id}/anchor`, which is the step that
needs a wallet because it builds the transaction the researcher signs:

```json
{ "submitter_address": "GABC..." }
```

It answers with the transaction to sign, and moves the dataset to `pending`:

```json
{
  "dataset_id": "3f1a...",
  "dataset_hash": "9c2b...",
  "unsigned_transaction_xdr": "AAAAAgAAAAB..."
}
```

Errors: `400` for a malformed address, `403` when the dataset is already bound
to a different address, `404` for an unknown dataset, and `409` once it is
`anchored` (there is nothing left to sign). A `pending` dataset can be anchored
again, which is what retrying a rejected signature looks like.

Because the address is what binds ownership, a dataset that was only analyzed
has no owner. `POST /batches` therefore claims any member that has no submitter
yet, and still refuses a member that belongs to somebody else.

Sending `submitter_address` to `POST /datasets` is **rejected with a `400`**
rather than ignored. Silently dropping it would return a body with no
transaction in it, and the caller would only find out at the signing step.

## Dataset statuses

| Status | Meaning |
|--------|---------|
| `analyzed` | Hashed and scored; no address, no transaction |
| `pending` | An anchor transaction (its own, or its batch's root) is awaiting a signature |
| `anchored` | The signed transaction was submitted and confirmed |
| `failed` | Submission was attempted and rejected |

## Supported upload formats

`POST /datasets` and the file mode of `POST /verify` accept three formats,
detected from the filename extension (case-insensitive):

| Extension | Hashing | Analysis |
|-----------|---------|----------|
| `.csv` | Canonical CSV (RFC 4180 parsing, UTF-8, normalized line endings, Unicode NFC, one numeric form rounded half-even to 6 d.p., original row order) | Parsed as CSV |
| `.json` | Same canonical CSV as the equivalent CSV upload | Parsed as CSV |
| `.xml` | Canonical XML bytes | Flattened with `pandas.read_xml` |

Uploads that carry the same information produce the same `dataset_hash`
regardless of formatting. CSV and JSON are normalized to one canonical CSV form
(so an integer stays an integer and hashes identically in both). `dataset_hash`
responses also carry the `canonicalization_version` of the rules that produced
them. XML is never
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
  "soroban_rpc": "connected",
  "network_passphrase": "Test SDF Network ; September 2015"
}
```

`soroban_rpc` is `"unreachable"` when the RPC node times out, errors, or
reports an unhealthy status. The probe timeout is configurable via
`SOROBAN_RPC_HEALTH_TIMEOUT_SECONDS` (default 3s). `status` describes the API
itself, so it remains `"ok"` while a dependency is down.

`network_passphrase` is the network transactions are built and verified
against (`SOROBAN_NETWORK_PASSPHRASE`). The frontend reads it to warn when a
connected wallet is on a different network: signing for the wrong one produces a
signature the contract rejects, and the rejection does not say why. It is served
from the backend rather than configured in the frontend because the transaction
is built server-side, so this is the only value that decides which signature
will be accepted.

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

Reports how much life the anchored entries have left, nested under `roots` and
`records`. Anchors are Persistent ledger entries, so if renewal stops working
they are eventually archived and verification silently stops answering — for
every dataset in a batch when a root goes, for one dataset when a standalone
record does. This endpoint is how that shows up as a number instead.

```json
{
  "enabled": true,
  "signer_configured": true,
  "renewal_window_days": 30,
  "entry_lifetime_days": 180.0,
  "roots": {
    "anchored": 12,
    "without_recorded_expiry": 0,
    "due_for_renewal": 2,
    "past_recorded_expiry": 0,
    "with_renewal_error": 0,
    "next_expiry_at": "2026-10-02T11:15:00+00:00",
    "last_renewed_at": "2026-09-01T03:00:12+00:00"
  },
  "records": {
    "anchored": 7,
    "without_recorded_expiry": 0,
    "due_for_renewal": 1,
    "past_recorded_expiry": 0,
    "with_renewal_error": 0,
    "next_expiry_at": "2026-09-20T08:02:41+00:00",
    "last_renewed_at": null
  }
}
```

The `records` block counts standalone anchors only. A dataset anchored in a
batch is covered by its batch root and has no record of its own, so it is
counted under `roots` instead.

Alert on `past_recorded_expiry` above zero, or on `with_renewal_error` growing,
under either kind: either means the renewal job has stopped keeping up.

Note that expiry is the deadline **recorded** when an entry was anchored or
renewed, derived from the contract's TTL budgets — it is not read back from the
ledger. Treat it as a drift detector: if the contract's budgets change, these
deadlines go stale and say so here rather than failing silently.

Renewal itself is a scheduled command, not an endpoint:

```bash
cd backend
python -m app.jobs.renew_ttl --dry-run   # list what would be renewed
python -m app.jobs.renew_ttl             # renew for real
```

It exits `0` on a clean run, `1` when any renewal failed (the failure is also
recorded on the batch), and `2` when the job is disabled or has no signing
account configured.
