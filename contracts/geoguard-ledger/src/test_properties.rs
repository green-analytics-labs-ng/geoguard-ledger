//! Property-based tests for Merkle verification and renewal arithmetic.
//!
//! `test.rs` pins specific examples; these assert invariants over generated
//! inputs, which is what catches the boundary and off-by-one cases a
//! hand-written example tends to miss.
//!
//! The crate is `#![no_std]`, so nothing here may name `std`: that is why the
//! collections are `soroban_sdk::Vec` and there is no printing. `proptest`
//! itself is a separate crate and links `std` on its own.

use proptest::prelude::*;
use soroban_sdk::{testutils::Address as _, Address, BytesN, Symbol, Vec};

use crate::test_support::{
    distinct_hashes, outsider_hash, quiet_env, record_ttl, setup, tamper, Tree,
};

proptest! {
    #![proptest_config(ProptestConfig::with_cases(48))]

    /// Completeness: every leaf of a batched tree has a proof that verifies.
    #[test]
    fn every_leaf_has_a_verifying_proof(base in any::<[u8; 32]>(), n in 1u32..=32) {
        let env = quiet_env();
        let (_, client) = setup(&env);
        let admin = Address::generate(&env);
        client.initialize(&admin);
        let submitter = Address::generate(&env);

        let hashes = distinct_hashes(&env, &base, n);
        let tree = Tree::build(&env, &hashes);
        let root = tree.root();
        client.anchor_root(&submitter, &root, &n);

        for i in 0..n {
            let hash = hashes.get(i).unwrap();
            prop_assert!(client.verify_inclusion(&root, &hash, &i, &tree.proof(&env, i)));
        }
    }

    /// Soundness: a proof for one dataset must not vouch for another.
    #[test]
    fn a_proof_does_not_verify_a_different_dataset(
        base in any::<[u8; 32]>(),
        n in 2u32..=16,
        pick in any::<u32>(),
    ) {
        let env = quiet_env();
        let (_, client) = setup(&env);
        let admin = Address::generate(&env);
        client.initialize(&admin);
        let submitter = Address::generate(&env);

        let index = pick % n;
        let hashes = distinct_hashes(&env, &base, n);
        let tree = Tree::build(&env, &hashes);
        let root = tree.root();
        client.anchor_root(&submitter, &root, &n);

        let proof = tree.proof(&env, index);
        let real = hashes.get(index).unwrap();
        prop_assert!(client.verify_inclusion(&root, &real, &index, &proof));

        // Same position, same proof, different dataset: must be rejected.
        let outsider = outsider_hash(&env, &base);
        prop_assert!(!client.verify_inclusion(&root, &outsider, &index, &proof));
    }

    /// Tampering with any sibling must break the recomputed root.
    #[test]
    fn a_tampered_sibling_breaks_the_proof(
        base in any::<[u8; 32]>(),
        n in 2u32..=16,
        pick in any::<u32>(),
    ) {
        let env = quiet_env();
        let (_, client) = setup(&env);
        let admin = Address::generate(&env);
        client.initialize(&admin);
        let submitter = Address::generate(&env);

        let index = pick % n;
        let hashes = distinct_hashes(&env, &base, n);
        let tree = Tree::build(&env, &hashes);
        let root = tree.root();
        client.anchor_root(&submitter, &root, &n);

        let proof = tree.proof(&env, index);
        let hash = hashes.get(index).unwrap();
        prop_assert!(client.verify_inclusion(&root, &hash, &index, &proof));

        let mut broken = Vec::new(&env);
        broken.push_back(tamper(&env, &proof.get(0).unwrap()));
        for i in 1..proof.len() {
            broken.push_back(proof.get(i).unwrap());
        }
        prop_assert!(!client.verify_inclusion(&root, &hash, &index, &broken));
    }

    /// An unanchored root must never verify, however well-formed the proof.
    #[test]
    fn an_unanchored_root_never_verifies(
        base in any::<[u8; 32]>(),
        n in 1u32..=16,
        pick in any::<u32>(),
    ) {
        let env = quiet_env();
        let (_, client) = setup(&env);
        let admin = Address::generate(&env);
        client.initialize(&admin);

        let index = pick % n;
        let hashes = distinct_hashes(&env, &base, n);
        let tree = Tree::build(&env, &hashes);

        // Deliberately do not anchor the root.
        prop_assert!(!client.verify_inclusion(
            &tree.root(),
            &hashes.get(index).unwrap(),
            &index,
            &tree.proof(&env, index)
        ));
    }

    /// In a power-of-two tree no node is self-paired, so the low bit of the
    /// index unambiguously selects the side: flipping it must break the proof.
    ///
    /// Odd-sized trees are exempt on purpose. There a trailing node is paired
    /// with itself, and `hash_node(x, x)` is symmetric, so the index genuinely
    /// carries no information at that level.
    #[test]
    fn index_side_matters_when_no_node_is_self_paired(
        base in any::<[u8; 32]>(),
        shift in 1u32..=5,
        pick in any::<u32>(),
    ) {
        let env = quiet_env();
        let (_, client) = setup(&env);
        let admin = Address::generate(&env);
        client.initialize(&admin);
        let submitter = Address::generate(&env);

        let n = 1u32 << shift;
        let index = pick % n;
        let hashes = distinct_hashes(&env, &base, n);
        let tree = Tree::build(&env, &hashes);
        let root = tree.root();
        client.anchor_root(&submitter, &root, &n);

        let proof = tree.proof(&env, index);
        let hash = hashes.get(index).unwrap();
        prop_assert!(client.verify_inclusion(&root, &hash, &index, &proof));
        prop_assert!(!client.verify_inclusion(&root, &hash, &(index ^ 1), &proof));
    }

    /// Renewal always leaves headroom below the requested target, so a call
    /// cannot silently no-op on an entry that already sits at the target.
    #[test]
    fn renewal_threshold_leaves_headroom(target in any::<u32>()) {
        let threshold = crate::renewal_threshold(target);
        prop_assert!(threshold <= target);
        if target == 0 {
            prop_assert_eq!(threshold, 0);
        } else {
            prop_assert!(threshold >= 1);
        }
        if target > 1 {
            prop_assert!(threshold < target);
        }
    }

    /// `extend_ttl` reaches exactly the requested target whenever the target is
    /// high enough for the renewal threshold to be met.
    #[test]
    fn extend_ttl_is_exact_above_the_write_time_bump(target in 3_300_000u32..=4_000_000u32) {
        let env = quiet_env();
        let (contract_id, client) = setup(&env);
        let admin = Address::generate(&env);
        client.initialize(&admin);
        let submitter = Address::generate(&env);

        let hash = BytesN::from_array(&env, &[7u8; 32]);
        client.anchor_hash(&submitter, &hash, &0, &Symbol::new(&env, "m"));

        client.extend_ttl(&hash, &target);
        prop_assert_eq!(record_ttl(&env, &contract_id, &hash), target);
    }
}
