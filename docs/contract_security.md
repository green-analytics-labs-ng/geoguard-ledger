# Contract Security & Fuzz Testing

This is the security coverage of the Soroban ledger contract
(`contracts/geoguard-ledger`). It records what the property tests actually
assert, the two defensive changes they drove, and the limits of this approach.

Gas cost is a separate concern — see [gas_audit.md](./gas_audit.md).

## Layers

| Layer | Where | What it pins |
|---|---|---|
| Unit tests | `src/test.rs` | Specific inputs and error codes. 29 tests. |
| Property tests | `src/test_properties.rs` | Invariants over generated inputs. 7 properties. |
| Gas regression | `src/test_gas.rs` | CPU/memory ceilings for cost-scaling operations. |
| Coverage-guided fuzz | `fuzz/` | `verify_inclusion` checked against an independent `sha2` reference over libFuzzer-explored inputs. |
| Deployed-contract smoke | `backend/tests/smoke_testnet.py` | Entry points exist on a *deployed* instance. |

Unit tests catch a regression you thought to write down. The property tests
exist for the cases you did not: odd tree shapes, an empty proof, a proof whose
length is nonsense, an index at the far end of `u32`.

The fuzz target covers the same verifier as the property tests but searches for
failing inputs using coverage feedback instead of a fixed generator, and checks
against a separately written reference rather than a fixed set of assertions.
See [The fuzz target](#the-fuzz-target).

> `test.rs` keeps the SDK's default of writing a JSON snapshot per test on drop.
> The property and gas modules call `test_support::quiet_env()` to switch that
> off — a property test builds one `Env` per generated case, so the default would
> scatter hundreds of snapshot files through a single `cargo test` run, none of
> them recording ledger state worth reviewing.

## What the properties assert

Each runs `PROPTEST_CASES` (default 48) generated cases.

| Property | Invariant |
|---|---|
| `every_leaf_has_a_verifying_proof` | **Completeness.** For a generated 32-byte base and any `n` in `1..=32`, every leaf's own proof verifies against the anchored root. |
| `a_proof_does_not_verify_a_different_dataset` | **Soundness.** A proof valid for one leaf must not verify a different dataset at the same index. |
| `a_tampered_sibling_breaks_the_proof` | **Tamper resistance.** Flipping a byte of any single sibling must break verification. |
| `an_unanchored_root_never_verifies` | A well-formed proof against a root that was never anchored returns `false`. |
| `index_side_matters_when_no_node_is_self_paired` | **Position binding.** In a power-of-two tree, the same proof at index `index ^ 1` must fail, so a leaf cannot be replayed at a neighbour's position. |
| `renewal_threshold_leaves_headroom` | `renewal_threshold(t) <= t`, and strictly `< t` for `t > 1`, so a renewal can never silently no-op on an entry already at its target. |
| `extend_ttl_is_exact_above_the_write_time_bump` | For targets in `3,300,000..=4,000,000`, `extend_ttl` leaves the record with **exactly** the requested TTL. |

Two details worth calling out, because they are the parts a naive version of
these tests gets wrong:

- **The index-side property excludes odd-sized trees on purpose.** An odd level
  pairs its trailing node with itself, and `hash_node(x, x)` is symmetric, so at
  that level the index genuinely carries no information. Asserting the property
  there would pin a bug rather than catch one.
- **The `n` ranges are bounded** (`1..=32`, `2..=16`, `shift 1..=5`) because each
  case anchors a real tree and the wide ranges would blow the case budget for
  little extra coverage. The 1,024-leaf extreme is covered by the gas tests.

## Hardening changes

Both came out of running the properties and the measurements, not from
speculation.

### Saturating counters instead of `+ 1`

`increment_submit_count`, `increment_total_anchored`, `increment_batch_count`,
and `increment_total_batches` now use `saturating_add(1)`.

The release profile sets `overflow-checks = true`, so a plain `+ 1` at
`u32::MAX` **aborts the transaction**. Reaching four billion anchors is not a
realistic state, but the two failure modes are not equivalent: a saturating
counter yields a wrong number, whereas a panic ends a call that had already done
its work. `test::increment_saturates_instead_of_aborting` drives the counter to
its ceiling and asserts the anchor still lands.

### A bound on proof length

`verify_inclusion` now rejects any `siblings` vector longer than
`MAX_PROOF_DEPTH = 32` before hashing anything.

The bound is exact rather than arbitrary: `index` is a `u32`, so a leaf position
needs at most 32 halvings to reach the root, and a longer path cannot describe a
position in any batch. It therefore never rejects a proof that could have been
genuine. The reason to bound it at all is budget — without the check, a caller
can hand over a path of arbitrary length and make the contract hash its way
through all of it before failing.

`test_gas::an_over_long_proof_is_rejected_without_walking_it` proves the
short-circuit is real rather than assumed: rejecting a 1,000-sibling proof costs
**exactly** the same as rejecting a 33-sibling one, so the loop is never entered.

## Running the fuzz campaign

```bash
cd contracts/geoguard-ledger

# Default: 48 cases per property, fast enough for every commit.
cargo test

# A heavier campaign. Raise the count and let it run longer.
PROPTEST_CASES=2000 cargo test test_properties
```

The last campaign run at `PROPTEST_CASES=2000` executed **14,000 generated
cases** (7 properties × 2,000) with no counterexamples, in 28.7s.

### Coverage-guided fuzzing

`fuzz/` is a `cargo-fuzz` (libFuzzer) target that drives the real
`verify_inclusion` entry point. It needs a nightly toolchain and `cargo-fuzz`:

```bash
rustup toolchain install nightly
cargo install cargo-fuzz --version 0.13.2 --locked

cd contracts/geoguard-ledger

# The harness on its own, on stable — no nightly needed to sanity-check it.
cargo test --manifest-path fuzz/Cargo.toml --test harness

# The real thing. AddressSanitizer is the cargo-fuzz default.
cargo +nightly fuzz run verify-inclusion

# Time-boxed, the way CI runs it (~4x the executions, ~3.7x faster to build).
cargo +nightly fuzz run --sanitizer none verify-inclusion -- -max_total_time=60
```

## The fuzz target

One case does three things, all against a fresh `Env` with a real tree anchored:

| Check | Assertion |
|---|---|
| Completeness | A genuine proof for a generated tree must verify. |
| Differential | For arbitrary dataset hash, index and sibling list, the contract's answer must equal the reference's. |
| Unanchored | A root that was never anchored must never verify. |

The completeness check is what keeps the rest honest: a verifier that returned
`false` for everything would satisfy the differential and unanchored checks
trivially.

The reference in `fuzz/src/harness.rs` is written from the documented scheme
(and mirrors `backend/app/services/merkle.py`) using the `sha2` crate, while the
contract hashes through the host crypto API. That is what makes a disagreement
meaningful rather than a restatement of the same code.

### Why the target compiles the contract's source

The contract's `[lib] crate-type` is `["cdylib"]`, and a `cdylib` cannot be
linked against. The obvious fix — adding `"rlib"` — was measured and rejected:
rustc then has to preserve the crate's whole `pub` surface, and the deployed wasm
grows from **11,942 to 25,621 bytes** (code section 5,611 → 17,755), with no
Cargo flag to avoid it.

So `fuzz/Cargo.toml` points its `[lib]` at `../src/lib.rs` instead. The contract's
manifest, and therefore the artifact, is untouched, and the target still exercises
the real code rather than a copy. The cost is that the fuzz manifest mirrors the
contract's dependencies, and CI fails if the two lockfiles resolve a different
`soroban-sdk` — because the fuzzer silently testing a different SDK than the
contract ships would be worse than no fuzzer.

### Throughput, and why the design looks like this

Under the fuzzer a case runs at roughly **450/s**, so CI's 60-second budget buys
about **27,000 cases** (about 6,900 under the slower ASAN default) — and since
each case makes 18 verification calls, roughly **half a million verifications**
per run. Two measured choices get it there:

- **One `Env` per case, many verifications per `Env`.** A fresh `Env` — register,
  initialize, anchor — costs about **0.38ms**, while a single `verify_inclusion`
  costs about **0.015ms**. Running 16 differential checks against that one setup
  costs roughly 3x a single-check case but makes 18 verification calls instead of
  one.
- **Not one `Env` for the whole run.** Reusing it was measured and rejected: the
  host accumulates every registered instance and stored entry, so per-case cost
  climbs from **3.2ms to over 10ms within 2,000 cases** — an order of magnitude
  slower than the flat 0.38ms of a fresh `Env` — while resident memory grows about
  **20KB per case**. A fresh `Env` also keeps a case's outcome a function of its
  input alone, which is what makes a reported crash reproducible.

### Evidence the target has teeth

A green fuzz run means nothing on its own, so the harness was checked by
injecting a real bug: swapping the two sides of the fold in `verify_inclusion`
(`hash_node(node, sibling)` ↔ `hash_node(sibling, node)`). The fuzzer found it
within seconds and shrank the reproducer to **3 bytes** (`ea0000`), reported by
the completeness check. That bug is reverted; no such input exists in the
current code.

### When a property fails

`proptest` shrinks the failing input to a minimal one and writes it to
`proptest-regressions/`. That directory is the regression suite: **commit it.**
The test then replays those seeds first on every subsequent run, so a case that
once failed can never silently start passing again.

## Coverage limits — read this before trusting the list

- **Neither the properties nor the fuzzer execute the deployed WASM.** Both call
  the contract through `soroban-sdk`'s test host, which links the contract's
  Rust natively. The real artifact is only exercised by a deploy plus the smoke
  test. Everything here is a strong check on the *logic*, not on the wasm.
- **The test host is not the network host.** These tests run against
  `soroban-sdk`'s test host, which models ledger behavior but is not the
  deployed protocol. A green suite is not a substitute for the testnet smoke
  test, which checks a real deployed instance.
- **The properties cover proof verification and TTL arithmetic.** They do not
  cover access control (`transfer_admin`, the auth requirements on anchoring),
  storage layout migration, or XDR round-tripping of the record types — those
  are pinned by the unit tests, not by generated inputs.
- **Arithmetic elsewhere is not fuzzed.** The saturating counters are tested by
  example. The TTL helpers are covered by a pure property, but the storage-write
  paths that consume them are only exercised at the values the tests choose.
