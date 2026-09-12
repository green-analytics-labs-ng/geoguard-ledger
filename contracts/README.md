# GeoGuard Ledger — Soroban Smart Contract

## Build

```bash
cargo build --target wasm32-unknown-unknown --release
```

## Optimize

The release profile in `Cargo.toml` already sets `opt-level = "z"`, `lto`, and
`strip`, which is what CI and the release workflow build with. To run the
`wasm-opt` pass on top of that:

```bash
stellar contract build --optimize
```

That writes to `target/wasm32v1-none/release/geoguard_ledger.wasm`, not the
`wasm32-unknown-unknown` path used above — pass `--wasm` if you deploy it.

## Test

```bash
cargo test --verbose
```

## Lint

```bash
cargo fmt --all -- --check
cargo clippy --target wasm32-unknown-unknown -- -D warnings
```

## Deploy to Testnet

Use the repository script rather than invoking the CLI by hand: it validates the
WASM path, extracts the deployed contract ID, and optionally initializes the
contract. CI's `Deploy to Testnet` workflow runs this same script.

```bash
DEPLOYER_SECRET=S... ./scripts/deploy_contract.sh --admin G... --write-env
```

Or with the CLI directly:

```bash
stellar contract deploy \
  --wasm target/wasm32-unknown-unknown/release/geoguard_ledger.wasm \
  --source-account <secret_key> \
  --network testnet
```

A deployment is permanent and creates a new contract ID; it does not replace a
previous one. Datasets anchored against an old instance stay bound to it, so any
drift between the deployed contract and this source is a real problem — see
[Smoke test](#smoke-test) below.

## Initialize

```bash
stellar contract invoke \
  --id <CONTRACT_ID> \
  --source-account <admin_secret> \
  --network testnet \
  -- initialize \
  --admin <admin_public_key>
```

## Invoke Functions

### Anchor a Hash

```bash
stellar contract invoke \
  --id <CONTRACT_ID> \
  --source-account <submitter_secret> \
  --network testnet \
  -- anchor_hash \
  --submitter <submitter_public_key> \
  --dataset_hash <64-char-hex> \
  --anomaly_score 420 \
  --model_version isoforest_v1
```

### Verify Integrity

```bash
stellar contract invoke \
  --id <CONTRACT_ID> \
  --network testnet \
  -- verify_integrity \
  --dataset_hash <64-char-hex>
```

### Anchor a Merkle Root (Batch)

```bash
stellar contract invoke \
  --id <CONTRACT_ID> \
  --source-account <submitter_secret> \
  --network testnet \
  -- anchor_root \
  --submitter <submitter_public_key> \
  --merkle_root <64-char-hex> \
  --leaf_count 128
```

### Verify Batch Inclusion

```bash
stellar contract invoke \
  --id <CONTRACT_ID> \
  --network testnet \
  -- verify_inclusion \
  --merkle_root <64-char-hex> \
  --dataset_hash <64-char-hex> \
  --index 0 \
  --siblings '["64-char-hex", "64-char-hex"]'
```

### Get Record Count

```bash
stellar contract invoke \
  --id <CONTRACT_ID> \
  --network testnet \
  -- get_record_count \
  --submitter <public_key>
```

### Get Total Anchored

```bash
stellar contract invoke \
  --id <CONTRACT_ID> \
  --network testnet \
  -- get_total_anchored
```

### Extend a TTL (Record or Root)

Renewal is permissionless: any funded account may push an expiry out, and a call
against an entry that is still well covered is a no-op.

```bash
stellar contract invoke \
  --id <CONTRACT_ID> \
  --source-account <payer_secret> \
  --network testnet \
  -- extend_ttl \
  --dataset_hash <64-char-hex> \
  --extend_to 3110400
```

Swap `extend_ttl`/`--dataset_hash` for `extend_root_ttl`/`--merkle_root` to renew
a batch root instead. The backend does both on a schedule
(`cd backend && python -m app.jobs.renew_ttl`).

## Smoke test

`backend/tests/smoke_testnet.py` checks a *deployed* contract rather than the
source: it confirms the entry points the backend calls actually exist on the
instance, then anchors a record, proves batch inclusion against an anchored
root, and renews both. A contract deployed before batching existed passes every
unit test while failing the first of those checks, which is the drift this
catches.

```bash
cd backend
CONTRACT_ID=C... uv run python -m tests.smoke_testnet --read-only   # no key, no fees
SMOKE_TEST_SIGNER_SECRET=S... uv run python -m tests.smoke_testnet  # full, spends fees
```

## Functions

| Function | Access | Description |
|----------|--------|-------------|
| `initialize(admin)` | Deploy-once | Sets the admin address. |
| `anchor_hash(submitter, hash, score, model)` | Auth required | Stores a new anchor record, extending its TTL to the full record budget on write. |
| `verify_integrity(hash)` | Read-only | Returns the record for a hash, or `None`. |
| `get_record_count(submitter)` | Read-only | Number of datasets anchored by submitter. |
| `get_total_anchored()` | Read-only | Global count of anchored datasets. |
| `extend_ttl(hash, extend_to)` | Public | Renews the TTL of a Persistent record once it drops below the renewal margin. |

Persistent entries are written with an explicit TTL bump (~180 days) rather than
inheriting the network's minimum persistent-entry TTL. Records need this most: a
record is written once and never modified, so without the bump it would be
archived within days and `verify_integrity` would stop answering for a dataset
nobody had tampered with. Renewal afterwards is permissionless and idempotent —
anyone may call `extend_ttl` / `extend_root_ttl`, and a call against an entry
that is already well covered is a no-op.
| `anchor_root(submitter, root, leaf_count)` | Auth required | Stores a Merkle root committing to a batch of datasets. |
| `get_root(root)` | Read-only | Returns the batch record for a root, or `None`. |
| `verify_inclusion(root, hash, index, siblings)` | Read-only | Verifies a Merkle inclusion proof against an anchored root. |
| `get_batch_count(submitter)` | Read-only | Number of Merkle roots anchored by submitter. |
| `get_total_batches()` | Read-only | Global count of anchored Merkle roots. |
| `extend_root_ttl(root, extend_to)` | Public | Renews the TTL of a Persistent batch root, using the same renewal margin. |
| `transfer_admin(new_admin)` | Admin only | Transfers admin rights. |

## Errors

Fallible functions return a structured contract error — they do not panic — so
clients can branch on the numeric code instead of parsing strings:

| Code | Variant | Meaning |
|:---:|---|---|
| 1 | `NotInitialized` | Contract has no admin; call `initialize` first. |
| 2 | `AlreadyInitialized` | `initialize` was already called. |
| 3 | `HashAlreadyAnchored` | The dataset hash already exists on-chain. |
| 4 | `HashNotFound` | `extend_ttl` was called for an unknown hash. |
| 5 | `Unauthorized` | Caller lacks the required authorization. |
| 6 | `RootAlreadyAnchored` | The Merkle root already exists on-chain. |
| 7 | `RootNotFound` | `extend_root_ttl` was called for an unknown root. |
| 8 | `EmptyBatch` | `anchor_root` was called with a `leaf_count` of 0. |

## Merkle Scheme

The batch layout is normative and implemented identically on-chain
(`src/merkle.rs`) and off-chain (`backend/app/services/merkle.py`):

- Leaf: `SHA256(0x00 || dataset_hash)`
- Internal node: `SHA256(0x01 || left || right)`
- A level with an odd number of nodes pairs its final node with itself.

Inclusion proofs list one sibling per level, bottom-up, and are checked by
halving the leaf index once per level.
