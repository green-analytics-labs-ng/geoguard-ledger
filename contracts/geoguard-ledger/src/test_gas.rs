//! Gas-cost regression tests for the operations whose cost scales with batch size.
//!
//! Soroban's test host records the CPU instructions and memory bytes a call
//! consumes, and that is what these assert against. Two caveats worth stating
//! plainly rather than leaving implied:
//!
//! - The host under-counts relative to real WASM execution, so these figures are
//!   a *relative* baseline, not a prediction of mainnet fees. They are stable
//!   run to run, which is what makes them usable as a regression guard.
//! - The limits carry deliberate headroom over the measured value, so an
//!   ordinary refactor does not trip them while a change that makes verification
//!   scale with the batch still does.
//!
//! Measured baselines (cpu instructions / memory bytes), captured with the same
//! setup each test below uses, so these are the numbers the ceilings guard:
//!
//! | operation                              | cpu     | memory |
//! |----------------------------------------|---------|--------|
//! | `verify_inclusion`, 1 leaf (depth 0)   |  47,826 | 30,400 |
//! | `verify_inclusion`, 1,024 leaves (10)  | 146,646 | 33,290 |
//! | rejected over-long proof               |  39,746 | 30,143 |
//! | `anchor_hash`                          | 148,502 | 60,087 |
//! | `anchor_root`                          | 160,694 | 60,178 |
//!
//! Each ceiling sits roughly 25% above its measurement — enough to absorb a
//! refactor, little enough that a change which makes verification scale with
//! the batch cannot slip through. See `docs/gas_audit.md`.
//!
//! These were re-based when soroban-sdk moved from 22 to 28, and it is worth
//! being precise about what moved. Nothing in the code they measure changed —
//! the same functions, the same arithmetic — yet every figure rose, and memory
//! rose several-fold on operations that barely allocate: a single-leaf
//! verification went from 3,624 bytes to 30,400. That is a change of *meter*,
//! not of contract. sdk 28 brings a new soroban-env-host, and the host is what
//! charges for instructions and bytes here.
//!
//! So the pre-28 table (31,193 / 131,083 / 23,006 / 105,137 / 113,796 cpu at
//! 3,624-16,882 bytes) is not comparable to this one, and a diff across the two
//! reads as a regression that never happened. What does still compare across it
//! is the *shape*: verification grows with proof depth rather than batch size,
//! and a rejected proof stays cheap because it short-circuits before the hashing
//! loop. That is the property these ceilings exist to protect, and the test below
//! checks the depth-scaling half of it directly rather than by proportion.

use soroban_sdk::{testutils::Address as _, Address, BytesN, Env, Symbol, Vec};

use crate::test_support::{distinct_hashes, quiet_env, setup, Tree};

/// `verify_inclusion` over a 1,024-leaf batch (a 10-level proof).
const MAX_DEPTH_INCLUSION_CPU: u64 = 185_000;

/// `verify_inclusion` over a single-leaf batch (no sibling path at all).
const SINGLE_LEAF_INCLUSION_CPU: u64 = 60_000;

/// A proof rejected before any hashing happens.
const REJECTED_PROOF_CPU: u64 = 50_000;

const ANCHOR_HASH_CPU: u64 = 185_000;
const ANCHOR_ROOT_CPU: u64 = 200_000;

struct Cost {
    cpu: u64,
    memory: u64,
}

/// Run `f` with the budget reset, and report only what `f` consumed.
fn measure<T>(env: &Env, f: impl FnOnce() -> T) -> (T, Cost) {
    env.cost_estimate().budget().reset_default();
    let value = f();
    let budget = env.cost_estimate().budget();
    (
        value,
        Cost {
            cpu: budget.cpu_instruction_cost(),
            memory: budget.memory_bytes_cost(),
        },
    )
}

/// Anchor a tree of `n` leaves and return everything needed to prove into it.
fn anchored_tree(
    env: &Env,
    n: u32,
) -> (
    crate::GeoGuardLedgerClient<'_>,
    BytesN<32>,
    Vec<BytesN<32>>,
    Vec<BytesN<32>>,
    u32,
) {
    let (_, client) = setup(env);
    let admin = Address::generate(env);
    client.initialize(&admin);
    let submitter = Address::generate(env);

    let hashes = distinct_hashes(env, &[9u8; 32], n);
    let tree = Tree::build(env, &hashes);
    let root = tree.root();
    client.anchor_root(&submitter, &root, &n);

    let index = n / 3;
    let proof = tree.proof(env, index);
    (client, root, hashes, proof, index)
}

#[test]
fn inclusion_at_practical_max_batch_depth_stays_within_budget() {
    let env = quiet_env();
    let (client, root, hashes, proof, index) = anchored_tree(&env, 1_024);

    let (verified, cost) = measure(&env, || {
        client.verify_inclusion(&root, &hashes.get(index).unwrap(), &index, &proof)
    });

    assert!(verified, "the generated proof must verify");
    assert!(
        cost.cpu < MAX_DEPTH_INCLUSION_CPU,
        "inclusion over 1,024 leaves cost {} cpu instructions, over the {} limit \
         (memory: {})",
        cost.cpu,
        MAX_DEPTH_INCLUSION_CPU,
        cost.memory
    );
}

#[test]
fn single_leaf_inclusion_stays_within_budget() {
    let env = quiet_env();
    let (client, root, hashes, proof, index) = anchored_tree(&env, 1);

    let (verified, cost) = measure(&env, || {
        client.verify_inclusion(&root, &hashes.get(index).unwrap(), &index, &proof)
    });

    assert!(verified);
    assert!(
        cost.cpu < SINGLE_LEAF_INCLUSION_CPU,
        "single-leaf inclusion cost {} cpu instructions, over the {} limit",
        cost.cpu,
        SINGLE_LEAF_INCLUSION_CPU
    );
}

/// The depth bound is only worth having if it actually short-circuits, so this
/// measures it. Walking 1,000 levels would cost roughly a hundred times the
/// figures below.
#[test]
fn an_over_long_proof_is_rejected_without_walking_it() {
    let env = quiet_env();
    let (_, client) = setup(&env);
    let admin = Address::generate(&env);
    client.initialize(&admin);
    let submitter = Address::generate(&env);

    let hashes = distinct_hashes(&env, &[7u8; 32], 1);
    let leaf = hashes.get(0).unwrap();
    let root = crate::merkle::hash_leaf(&env, &leaf);
    client.anchor_root(&submitter, &root, &1);

    let padded = |len: u32| {
        let mut proof = Vec::new(&env);
        for i in 0..len {
            proof.push_back(BytesN::from_array(&env, &[(i % 251) as u8; 32]));
        }
        proof
    };

    // One level past the bound, and one far past it.
    let just_over = padded(33);
    let far_over = padded(1_000);

    let (short_ok, short) = measure(&env, || {
        client.verify_inclusion(&root, &leaf, &0, &just_over)
    });
    let (long_ok, long) = measure(&env, || {
        client.verify_inclusion(&root, &leaf, &0, &far_over)
    });

    assert!(!short_ok, "a 33-level path cannot be valid");
    assert!(!long_ok, "a 1,000-level path cannot be valid");

    assert!(
        long.cpu <= short.cpu * 2,
        "cost grew with proof length ({} -> {}), so the depth bound is not \
         short-circuiting before the hashing loop",
        short.cpu,
        long.cpu
    );

    // Cheap for the same reason: rejection happens before any hashing.
    assert!(
        long.cpu < MAX_DEPTH_INCLUSION_CPU,
        "rejecting an over-long proof cost {} cpu instructions, which is not \
         cheaper than verifying a real 10-level proof",
        long.cpu
    );
    assert!(
        long.cpu < REJECTED_PROOF_CPU,
        "rejecting an over-long proof cost {} cpu instructions against a {} \
         baseline (memory: {})",
        long.cpu,
        REJECTED_PROOF_CPU,
        long.memory
    );
}

#[test]
fn anchoring_stays_within_budget() {
    let env = quiet_env();
    let (_, client) = setup(&env);
    let admin = Address::generate(&env);
    client.initialize(&admin);
    let submitter = Address::generate(&env);

    let hash = BytesN::from_array(&env, &[1u8; 32]);
    let (_, hash_cost) = measure(&env, || {
        client.anchor_hash(&submitter, &hash, &5_000, &Symbol::new(&env, "v1"))
    });

    let root = BytesN::from_array(&env, &[2u8; 32]);
    let (_, root_cost) = measure(&env, || client.anchor_root(&submitter, &root, &7));

    assert!(
        hash_cost.cpu < ANCHOR_HASH_CPU,
        "anchor_hash cost {} cpu instructions, over the {} limit",
        hash_cost.cpu,
        ANCHOR_HASH_CPU
    );
    assert!(
        root_cost.cpu < ANCHOR_ROOT_CPU,
        "anchor_root cost {} cpu instructions, over the {} limit",
        root_cost.cpu,
        ANCHOR_ROOT_CPU
    );
}
