# GeoGuard Ledger — Backend

FastAPI service behind GeoGuard Ledger. It ingests geochemical datasets,
canonicalizes and SHA-256 hashes them, scores them for anomalies, and prepares
and submits anchors to the `geoguard-ledger` Soroban contract.

Project-wide documentation lives in [`../docs`](../docs):

| Document | Covers |
|---|---|
| [`architecture.md`](../docs/architecture.md) | Why Stellar/Soroban, SHA-256, and Isolation Forest |
| [`api_reference.md`](../docs/api_reference.md) | HTTP endpoints and payloads |
| [`deployment.md`](../docs/deployment.md) | Deployment, and the operational keys the TTL job needs |

## Layout

| Path | Holds |
|---|---|
| `app/api/v1/` | Route handlers (`datasets`, `batches`, `verify`, `maintenance`, `health`) |
| `app/services/` | Canonicalization, hashing, Merkle trees, Soroban client, anomaly detection |
| `app/models/` | SQLAlchemy models (request/response schemas live with their routes) |
| `app/jobs/` | Scheduled work — currently TTL renewal |
| `alembic/` | Schema migrations |
| `tests/` | Pytest suite (SQLite-backed; no network required) |

## Running it

```bash
uv sync --dev                                  # install dependencies
cp .env.example .env                           # local defaults (see the note below)
uv run alembic upgrade head                    # apply migrations
uv run uvicorn app.main:app --reload           # serve on :8000
```

The app refuses to start with an empty `API_KEYS` unless
`ALLOW_UNAUTHENTICATED_WRITES=true` opts into it, so an open write API is a
deliberate, development-only choice rather than a default. `.env.example` sets
that opt-in for local work; set `API_KEYS` instead for anything that is not a
local checkout. Starting without a key also logs a warning — see
[`../docs/api_reference.md`](../docs/api_reference.md#authentication).

## Command-line entry points

Installing the project also installs its console scripts, so a scheduler can
invoke them by name instead of by module path:

| Command | Purpose |
|---|---|
| `geoguard-renew-ttl` | Renew anchored entries whose on-chain TTL is close to lapsing |

Both `geoguard-renew-ttl` and `python -m app.jobs.renew_ttl` run the same job.
Check what a run would do before letting it spend fees:

```bash
uv run geoguard-renew-ttl --dry-run
```

It exits `0` when clean, `1` if a renewal failed, and `2` when the job is
disabled or has no signing key — see [`../docs/deployment.md`](../docs/deployment.md)
for the required settings.
