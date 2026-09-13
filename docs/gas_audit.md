# Contract Gas & Size Audit

Cost report for the Soroban ledger contract (`contracts/geoguard-ledger`),
covering the release profile, one measured hot-path change, and the regression
ceilings that keep both from drifting.

Every figure below was measured on the Soroban test host from a clean harness
that mirrors the corresponding test in `src/test_gas.rs`. They reproduce
exactly, run to run. See [Reproducing](#reproducing).

## Result summary

| Lever | Outcome |
|---|---|
| Release profile | Already tuned (`opt-level = "z"`, `lto`, `codegen-units = 1`, `strip`, `panic = "abort"`). **Left unchanged** — nothing measured justified a change. |
| `overflow-checks` | Tested turning it **off**: **0 bytes saved**. Kept **on** for its safety value. |
| Hash helper allocation | Fixed-size arrays instead of `Bytes`: **−29.4% CPU / −45.0% memory** on a depth-10 inclusion proof. |
| Proof-length bound | Rejecting an over-long proof costs the same at 33 and 1,000 siblings — **O(1), not O(length)**. |
| WASM artifact | **11,942 bytes**, 18% of the 64 KB CI threshold. |

## 1. Release profile — no change

`Cargo.toml` already builds with:

```toml
[profile.release]
opt-level = "z"      # optimize for size, not speed
lto = true
codegen-units = 1
strip = true
panic = "abort"
overflow-checks = true
```

`overflow-checks = true` in a release profile is unusual, so it was measured
rather than assumed. Turning it off produced a WASM artifact of **exactly the
same size** (11,942 bytes both ways — the optimizer elides most of the checks,
and `panic = "abort"` leaves no unwinding machinery to strip). Since it costs
nothing measurable it stays: it is what makes an unchecked arithmetic bug fail
loudly instead of wrapping silently, and the counters were made saturating so a
legitimate ceiling does not trip it (see
[contract_security.md](./contract_security.md)).

## 2. Hash helpers — the one optimization

`merkle.rs`'s `hash_leaf` and `hash_node` built each SHA-256 preimage by pushing
and appending onto a `soroban_sdk::Bytes`, which allocates in the host's linear
memory. They now fill a fixed-size stack array and convert once:

```rust
// before: Bytes::new + push_back + append ×2
// after:
let mut payload = [0u8; 65];
payload[0] = NODE_PREFIX;
payload[1..33].copy_from_slice(&left.to_array());
payload[33..].copy_from_slice(&right.to_array());
env.crypto().sha256(&Bytes::from_array(env, &payload)).to_bytes()
```

`verify_inclusion` performs one hash per level, so the saving scales with proof
depth. Measured in an identical harness, before and after (cpu instructions /
memory bytes):

| Operation | Before | After | Δ CPU | Δ memory |
|---|---|---|---|---|
| `verify_inclusion`, depth 0 (1 leaf) | 34,112 / 3,881 | 31,193 / 3,624 | −8.6% | −6.6% |
| `verify_inclusion`, depth 1 (2 leaves) | 49,263 / 4,620 | 41,182 / 3,881 | −16.4% | −16.0% |
| `verify_inclusion`, depth 5 (32 leaves) | 109,867 / 7,576 | 81,138 / 4,909 | −26.1% | −35.2% |
| `verify_inclusion`, depth 10 (1,024 leaves) | 185,622 / 11,271 | **131,083 / 6,194** | **−29.4%** | **−45.0%** |
| `anchor_hash` | 105,137 / 14,921 | 105,137 / 14,921 | 0 | 0 |
| `anchor_root` | 113,796 / 16,882 | 113,796 / 16,882 | 0 | 0 |
| rejected over-long proof | 23,006 / 3,399 | 23,006 / 3,399 | 0 | 0 |

**The two anchor rows are the important ones.** They are byte-for-byte
unchanged, which is positive evidence that the optimization is scoped to the
hashing path and does not touch storage, TTL bumps, or the counters. The delta
grows monotonically with depth exactly as the model predicts (8.6% at one hash,
29.4% at eleven), rather than being a flat win that would suggest the
measurement was picking up something else.

Correctness is unchanged: the preimage byte layout is identical, so roots and
proofs are identical. The 29 unit tests and the off-chain agreement tests
(`backend/tests/test_merkle.py`) pass with the same expected values, which is
the evidence that this is an optimization and not a behavior change.

## 3. Proof-length bound

`verify_inclusion` rejects a `siblings` vector longer than
`MAX_PROOF_DEPTH = 32` before entering the hashing loop. `index` is a `u32`, so
no genuine path exceeds 32 levels — the bound never rejects a valid proof.

The point is that rejection is **O(1), not O(path length)**:

| Rejected proof | CPU | Memory |
|---|---|---|
| 33 siblings | 23,006 | 3,399 |
| 1,000 siblings | 23,006 | 3,399 |

Identical to the instruction, which is the proof that the loop is never entered.
Without the bound, the 1,000-sibling case would hash ~1,000 times before
failing — roughly ten times the work of verifying a real 1,024-leaf proof, on a
call whose only possible outcome is `false`.

`test_gas::an_over_long_proof_is_rejected_without_walking_it` asserts this and
says so in its failure message, so a refactor that moves the check inside the
loop fails loudly instead of quietly getting slower.

## 4. Regression ceilings

`src/test_gas.rs` asserts CPU ceilings with ~25% headroom: wide enough to absorb
an ordinary refactor or an SDK patch, narrow enough that a change making
verification scale with the batch cannot pass.

| Operation | Measured | Ceiling | Headroom |
|---|---|---|---|
| `verify_inclusion`, 1 leaf | 31,193 | 40,000 | +28% |
| `verify_inclusion`, 1,024 leaves | 131,083 | 165,000 | +26% |
| rejected over-long proof | 23,006 | 30,000 | +30% |
| `anchor_hash` | 105,137 | 130,000 | +24% |
| `anchor_root` | 113,796 | 140,000 | +23% |

Only CPU is asserted. Memory is reported in the failure messages but not
guarded: it is the noisier of the two and the CPU figure already moves with the
allocation behavior this audit targets.

Measurement resets the budget before the call so only the operation under test
is counted:

```rust
env.cost_estimate().budget().reset_default();
let value = f();
let budget = env.cost_estimate().budget();
```

## 5. WASM size

```
target/wasm32-unknown-unknown/release/geoguard_ledger.wasm   11,942 bytes
```

CI (`contract-test.yml`) warns above 65,536 bytes, so there is 53 KB of headroom
and no size pressure to trade against. `stellar contract build --optimize` adds
a `wasm-opt` pass for deployments that want a further reduction; CI does not run
it, so the size above is the plain release build — the same artifact CI checks.

## Limits of these numbers

- **The test host estimates cost; it does not execute the WASM.** These figures
  are a **relative** baseline for regression detection, not a prediction of
  mainnet fees. Read the ceilings as "did this get worse?", never as "what will
  this cost?".
- **The figures are harness-specific.** Soroban charges for storage writes based
  on what already exists, so an operation's cost depends on the ledger state the
  test set up. The numbers above come from the exact setup each test uses, which
  is what makes them comparable — they are not a property of the function alone.
- **Ceilings are per-operation, not per-transaction.** A transaction that anchors
  a root and then verifies an inclusion pays both, plus the network's own
  overhead. Compare against the sum, never against a single row.
- **`opt-level = "z"` trades speed for size**, which is the right call here: the
  workload is a handful of SHA-256 hashes, so optimizing for size does not
  meaningfully change wall-clock cost, and it keeps the artifact far inside the
  deploy limit.
- **The off-chain Merkle implementation is not benchmarked.**
  `backend/app/services/merkle.py` must agree with this contract byte-for-byte
  (see `contracts/README.md`); its performance is out of scope here.

## Reproducing

```bash
cd contracts/geoguard-ledger

# Assert the ceilings.
cargo test test_gas -- --nocapture

# WASM artifact size (the same artifact CI measures).
cargo build --target wasm32-unknown-unknown --release
wc -c target/wasm32-unknown-unknown/release/geoguard_ledger.wasm
```

To re-derive the baselines rather than assert them, add a temporary test in the
style of the ones above that reports the budget instead of comparing it. Because
the crate is `#![no_std]`, that test must report through `panic!("{:?}", ...)` —
there is no `format!` or `String` available.
