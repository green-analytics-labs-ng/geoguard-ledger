# GeoGuard Ledger — Soroban Smart Contract

## Build

```bash
cargo build --target wasm32-unknown-unknown --release
```

## Optimize

```bash
soroban contract optimize \
  --wasm target/wasm32-unknown-unknown/release/geoguard_ledger.wasm
```

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

```bash
soroban contract deploy \
  --wasm target/wasm32-unknown-unknown/release/geoguard_ledger.wasm \
  --source <secret_key> \
  --network testnet
```

## Initialize

```bash
soroban contract invoke \
  --id <CONTRACT_ID> \
  --source <admin_secret> \
  --network testnet \
  -- initialize \
  --admin <admin_public_key>
```

## Invoke Functions

### Anchor a Hash

```bash
soroban contract invoke \
  --id <CONTRACT_ID> \
  --source <submitter_secret> \
  --network testnet \
  -- anchor_hash \
  --submitter <submitter_public_key> \
  --dataset_hash <64-char-hex> \
  --anomaly_score 420 \
  --model_version isoforest_v1
```

### Verify Integrity

```bash
soroban contract invoke \
  --id <CONTRACT_ID> \
  --network testnet \
  -- verify_integrity \
  --dataset_hash <64-char-hex>
```

### Anchor a Merkle Root (Batch)

```bash
soroban contract invoke \
  --id <CONTRACT_ID> \
  --source <submitter_secret> \
  --network testnet \
  -- anchor_root \
  --submitter <submitter_public_key> \
  --merkle_root <64-char-hex> \
  --leaf_count 128
```

### Verify Batch Inclusion

```bash
soroban contract invoke \
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
soroban contract invoke \
  --id <CONTRACT_ID> \
  --network testnet \
  -- get_record_count \
  --submitter <public_key>
```

### Get Total Anchored

```bash
soroban contract invoke \
  --id <CONTRACT_ID> \
  --network testnet \
  -- get_total_anchored
```

## Functions

| Function | Access | Description |
|----------|--------|-------------|
| `initialize(admin)` | Deploy-once | Sets the admin address. |
| `anchor_hash(submitter, hash, score, model)` | Auth required | Stores a new anchor record. |
| `verify_integrity(hash)` | Read-only | Returns the record for a hash, or `None`. |
| `get_record_count(submitter)` | Read-only | Number of datasets anchored by submitter. |
| `get_total_anchored()` | Read-only | Global count of anchored datasets. |
| `extend_ttl(hash, extend_to)` | Public | Renews the TTL of a Persistent record once it drops below the renewal margin. |
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
