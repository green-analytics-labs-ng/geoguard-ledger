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
| Deployed-contract smoke | `backend/tests/smoke_testnet.py` | Entry points exist on a *deployed* instance. |

Unit tests catch a regression you thought to write down. The property tests
exist for the cases you did not: odd tree shapes, an empty proof, a proof whose
length is nonsense, an index at the far end of `u32`.

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

### When a property fails

`proptest` shrinks the failing input to a minimal one and writes it to
`proptest-regressions/`. That directory is the regression suite: **commit it.**
The test then replays those seeds first on every subsequent run, so a case that
once failed can never silently start passing again.

## Coverage limits — read this before trusting the list

- **This is property-based testing, not coverage-guided fuzzing.** There is no
  `cargo-fuzz`/libFuzzer target. `cargo-fuzz` builds a `std` binary harness,
  while this crate is `#![no_std]` and compiles to `wasm32-unknown-unknown`; a
  fuzz target would need its own crate and a non-contract build of the logic.
  The high-case `proptest` campaign is the practical substitute, and it is
  *input-space* fuzzing over the arguments, not over the WASM.
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
