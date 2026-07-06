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
| `extend_ttl(hash, extend_to)` | Public | Extends TTL for a Persistent record. |
| `transfer_admin(new_admin)` | Admin only | Transfers admin rights. |
