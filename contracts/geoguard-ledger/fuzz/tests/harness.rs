//! Stable-Rust verification of the fuzz harness.
//!
//! libFuzzer needs a nightly toolchain, so the harness would otherwise only ever
//! be exercised on a machine that has one. These tests are the ordinary `cargo
//! test` path: they run the same [`harness::check`] the fuzzer calls, over
//! generated inputs, and confirm the reference model's invariants directly.
//!
//! They are not a substitute for fuzzing — they sample a fixed 300 inputs rather
//! than searching driven by coverage — but they do prove the oracle in
//! `src/harness.rs` agrees with the contract today.

#[path = "../src/harness.rs"]
mod harness;

/// Inputs sampled by `check_agrees_with_the_contract_across_generated_inputs`.
const CASES: u64 = 300;

/// xorshift64, so the sample is varied but reproducible run to run.
fn next(state: &mut u64) -> u64 {
    let mut x = *state;
    x ^= x << 13;
    x ^= x >> 7;
    x ^= x << 17;
    *state = x;
    x
}

#[test]
fn check_agrees_with_the_contract_across_generated_inputs() {
    let mut state = 0x9E37_79B9_7F4A_7C15u64;
    let mut buffer = vec![0u8; 256];

    for _ in 0..CASES {
        // Vary the length too: the harness wraps its reader, so short inputs
        // reuse bytes and exercise different derivations than long ones.
        let len = 1 + next(&mut state) as usize % buffer.len();
        for byte in buffer[..len].iter_mut() {
            *byte = next(&mut state) as u8;
        }
        harness::check(&buffer[..len]);
    }
}

#[test]
fn check_handles_degenerate_inputs() {
    harness::check(&[]);
    harness::check(&[0u8; 512]);

    for len in [1usize, 2, 7, 31, 32, 33, 64, 1024] {
        harness::check(&vec![0xA5u8; len]);
        harness::check(&vec![0u8; len]);
    }
}

/// The depth bound is inclusive at 32, so a 32-level path is still evaluated
/// while a 33-level one is rejected outright. Pinning both sides matters: an
/// off-by-one here would reject genuine proofs for large batches.
#[test]
fn the_reference_enforces_the_depth_bound_exactly() {
    let dataset_hash = [0x11u8; 32];

    let at_bound = vec![[0x22u8; 32]; harness::MAX_PROOF_DEPTH];
    let over_bound = vec![[0x22u8; 32]; harness::MAX_PROOF_DEPTH + 1];

    // Fold the 32-level path by hand to get the root it legitimately produces.
    let mut node = harness::reference_hash_leaf(&dataset_hash);
    let mut idx = 0u32;
    for sibling in &at_bound {
        node = if idx % 2 == 0 {
            harness::reference_hash_node(&node, sibling)
        } else {
            harness::reference_hash_node(sibling, &node)
        };
        idx /= 2;
    }

    assert!(
        harness::reference_verify(&node, &dataset_hash, 0, &at_bound),
        "a 32-level proof must still be evaluated"
    );
    assert!(
        !harness::reference_verify(&node, &dataset_hash, 0, &over_bound),
        "a 33-level proof must be rejected"
    );
}
