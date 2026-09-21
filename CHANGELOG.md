# Changelog

All notable changes to GeoGuard Ledger are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Entries for a version in development live under `Unreleased` until it is tagged.

Because an anchored hash cannot be un-anchored, a change to how a hash is
computed is always a **breaking change**, however small it looks: digests taken
before it are no longer reproducible. Those entries say so explicitly.

## [Unreleased]

## [0.3.0] - 2026-09-19

### ⚠️ Breaking changes

- **Canonicalization v1 changes every `dataset_hash`.** Uploads are now
  normalized further before hashing: every cell is Unicode NFC, integers,
  decimals, and scientific notation are rendered as one numeric form (exact,
  rounded half-even to 6 decimal places), and file order is preserved rather
  than sorted. The same file uploaded under 0.2.0 and under this version
  produces different digests, so a dataset anchored with the old rules cannot
  be reproduced by the new code. Responses that carry a hash now also carry
  `canonicalization_version` so a verifier can tell which rule set a digest came
  from. See [docs/canonicalization.md](docs/canonicalization.md).

### Added

- Merkle batch anchoring: several datasets anchored under one root, with an
  inclusion proof per dataset and batch membership shown on the dataset pages.
- API-key authentication (`X-API-Key`) for upload and anchoring, validated in
  constant time. Verification and health stay public, and the frontend sends the
  key only to the endpoints that expect it.
- Rate limiting on the upload and analysis endpoints.
- TTL renewal job (`geoguard-renew-ttl`) with a documented exit-code contract
  for alerting, and renewal of standalone records as well as batch roots.
- XML upload support alongside CSV and JSON.
- A coverage floor for the backend suite, and coverage artifacts with a
  per-pull-request delta comment.
- Supply-chain checks in CI: `pip-audit`, `npm audit --omit=dev`, `cargo audit`,
  a Dependabot configuration for all four ecosystems, and CodeQL for Python and
  TypeScript.
- [SECURITY.md](SECURITY.md), with the private disclosure channels and scope.

### Changed

- A duplicate anchor is reported as a conflict (HTTP 409) instead of an error.
- The local Postgres is bound to loopback and the images run as non-root; the
  backend refuses to boot on an unsafe deployment configuration and CORS origins
  are pinned rather than reflected.

### Fixed

- The CSV parser follows RFC 4180, so quoted fields containing delimiters,
  escaped quotes, and CRLF line endings parse the same way they are hashed.
- Unused schema and storage stubs removed; the schema comes from Alembic alone,
  and the migration drift check can actually detect drift.

## [0.2.0] - 2026-09-11

The last version before tags were cut, so there is no `v0.2.0` on the remote to
compare against.

- Soroban contract with anchored hashes, Merkle roots, and per-record TTLs.
- FastAPI backend: CSV/JSON ingestion, canonicalization, SHA-256 hashing, and
  anomaly scoring.
- React frontend: upload with preview, dataset list and detail, and
  hash-or-file verification.
- Wallet connection through Freighter, with the contract the local stack uses
  pinned in `docker-compose.yml`.
