#[cfg(test)]
mod tests {
    use soroban_sdk::{
        testutils::{storage::Persistent as _, Address as _, MockAuth, MockAuthInvoke},
        vec, Address, BytesN, Env, IntoVal, Symbol,
    };

    use crate::{storage::DataKey, Error, GeoGuardLedgerClient};

    fn make_hash(env: &Env, data: &[u8; 32]) -> BytesN<32> {
        BytesN::from_array(env, data)
    }

    /// Register the contract with all auths mocked and return its address and client.
    fn setup_env(env: &Env) -> (Address, GeoGuardLedgerClient<'_>) {
        env.mock_all_auths();
        let contract_id = env.register(crate::GeoGuardLedger, ());
        let client = GeoGuardLedgerClient::new(env, &contract_id);
        (contract_id, client)
    }

    /// Remaining TTL (in ledgers) of a stored anchor record.
    fn record_ttl(env: &Env, contract_id: &Address, hash: &BytesN<32>) -> u32 {
        env.as_contract(contract_id, || {
            env.storage()
                .persistent()
                .get_ttl(&DataKey::Record(hash.clone()))
        })
    }

    /// Remaining TTL (in ledgers) of a stored Merkle root.
    fn root_ttl(env: &Env, contract_id: &Address, root: &BytesN<32>) -> u32 {
        env.as_contract(contract_id, || {
            env.storage()
                .persistent()
                .get_ttl(&DataKey::Root(root.clone()))
        })
    }

    #[test]
    fn test_initialize() {
        let env = Env::default();
        let (_, client) = setup_env(&env);
        let admin = Address::generate(&env);
        client.initialize(&admin);
        assert_eq!(client.get_total_anchored(), 0);
    }

    #[test]
    fn test_initialize_twice_returns_already_initialized() {
        let env = Env::default();
        let (_, client) = setup_env(&env);
        let admin = Address::generate(&env);
        client.initialize(&admin);

        let err = client.try_initialize(&admin).unwrap_err();
        assert_eq!(err.unwrap(), Error::AlreadyInitialized);
    }

    #[test]
    fn test_anchor_and_verify() {
        let env = Env::default();
        let (_, client) = setup_env(&env);
        let admin = Address::generate(&env);
        client.initialize(&admin);
        let submitter = Address::generate(&env);
        let hash = make_hash(&env, &[1u8; 32]);

        let record =
            client.anchor_hash(&submitter, &hash, &420, &Symbol::new(&env, "isoforest_v1"));

        assert_eq!(record.dataset_hash, hash);
        assert_eq!(record.anomaly_score, 420);
        assert_eq!(record.submitter, submitter);

        let stored = client.verify_integrity(&hash);
        assert!(stored.is_some());
        assert_eq!(stored.unwrap().dataset_hash, hash);

        let unknown = make_hash(&env, &[99u8; 32]);
        assert!(client.verify_integrity(&unknown).is_none());
    }

    #[test]
    fn test_no_double_anchor() {
        let env = Env::default();
        let (_, client) = setup_env(&env);
        let admin = Address::generate(&env);
        client.initialize(&admin);
        let submitter = Address::generate(&env);
        let hash = make_hash(&env, &[1u8; 32]);

        client.anchor_hash(&submitter, &hash, &0, &Symbol::new(&env, "isoforest_v1"));

        let err = client
            .try_anchor_hash(&submitter, &hash, &0, &Symbol::new(&env, "isoforest_v1"))
            .unwrap_err();
        assert_eq!(err.unwrap(), Error::HashAlreadyAnchored);
    }

    #[test]
    fn test_record_count() {
        let env = Env::default();
        let (_, client) = setup_env(&env);
        let admin = Address::generate(&env);
        client.initialize(&admin);
        let submitter = Address::generate(&env);

        assert_eq!(client.get_record_count(&submitter), 0);

        client.anchor_hash(
            &submitter,
            &make_hash(&env, &[1u8; 32]),
            &100,
            &Symbol::new(&env, "v1"),
        );
        assert_eq!(client.get_record_count(&submitter), 1);

        client.anchor_hash(
            &submitter,
            &make_hash(&env, &[2u8; 32]),
            &200,
            &Symbol::new(&env, "v1"),
        );
        assert_eq!(client.get_record_count(&submitter), 2);
        assert_eq!(client.get_total_anchored(), 2);
    }

    #[test]
    fn test_extend_ttl_renews_to_the_requested_target() {
        let env = Env::default();
        let (contract_id, client) = setup_env(&env);
        let admin = Address::generate(&env);
        client.initialize(&admin);
        let submitter = Address::generate(&env);
        let hash = make_hash(&env, &[1u8; 32]);

        client.anchor_hash(&submitter, &hash, &0, &Symbol::new(&env, "v1"));
        client.extend_ttl(&hash, &500_000);

        assert_eq!(record_ttl(&env, &contract_id, &hash), 500_000);
    }

    #[test]
    fn test_extend_ttl_is_a_noop_while_the_record_is_well_covered() {
        let env = Env::default();
        let (contract_id, client) = setup_env(&env);
        let admin = Address::generate(&env);
        client.initialize(&admin);
        let submitter = Address::generate(&env);
        let hash = make_hash(&env, &[1u8; 32]);

        client.anchor_hash(&submitter, &hash, &0, &Symbol::new(&env, "v1"));
        client.extend_ttl(&hash, &1_000_000);

        // Ask for a target barely above the current TTL. The renewal threshold
        // sits TTL_RENEWAL_MARGIN below the target, so the record is already well
        // covered and must not be touched. The old `extend_ttl(key, target,
        // target)` form would have renewed it here.
        client.extend_ttl(&hash, &1_050_000);

        assert_eq!(record_ttl(&env, &contract_id, &hash), 1_000_000);
    }

    #[test]
    fn test_extend_ttl_nonexistent() {
        let env = Env::default();
        let (_, client) = setup_env(&env);
        let admin = Address::generate(&env);
        client.initialize(&admin);
        let hash = make_hash(&env, &[99u8; 32]);

        let err = client
            .try_extend_ttl(&hash, &(env.ledger().sequence() + 500_000))
            .unwrap_err();
        assert_eq!(err.unwrap(), Error::HashNotFound);
    }

    #[test]
    fn test_transfer_admin() {
        let env = Env::default();
        let (_, client) = setup_env(&env);
        let admin = Address::generate(&env);
        client.initialize(&admin);
        let new_admin = Address::generate(&env);

        client.transfer_admin(&new_admin);
    }

    #[test]
    #[should_panic]
    fn test_transfer_admin_unauthorized() {
        let env = Env::default();
        let contract_id = env.register(crate::GeoGuardLedger, ());
        let client = GeoGuardLedgerClient::new(&env, &contract_id);

        let admin = Address::generate(&env);
        client.initialize(&admin);

        // Authorize an address that is *not* the admin. The contract still
        // requires the current admin's auth, so the transfer must be rejected.
        let imposter = Address::generate(&env);
        let new_admin = Address::generate(&env);
        env.mock_auths(&[MockAuth {
            address: &imposter,
            invoke: &MockAuthInvoke {
                contract: &contract_id,
                fn_name: "transfer_admin",
                args: (&new_admin,).into_val(&env),
                sub_invokes: &[],
            },
        }]);

        client.transfer_admin(&new_admin);
    }

    #[test]
    fn test_state_changing_calls_require_initialization() {
        let env = Env::default();
        // Register without initializing; do not mock auths so a genuine
        // auth failure cannot be confused with the missing-admin error.
        let contract_id = env.register(crate::GeoGuardLedger, ());
        let client = GeoGuardLedgerClient::new(&env, &contract_id);
        let hash = make_hash(&env, &[1u8; 32]);
        let who = Address::generate(&env);

        assert_eq!(
            client
                .try_anchor_hash(&who, &hash, &0, &Symbol::new(&env, "v1"))
                .unwrap_err()
                .unwrap(),
            Error::NotInitialized
        );
        assert_eq!(
            client.try_extend_ttl(&hash, &500_000).unwrap_err().unwrap(),
            Error::NotInitialized
        );
        assert_eq!(
            client.try_transfer_admin(&who).unwrap_err().unwrap(),
            Error::NotInitialized
        );
    }

    #[test]
    fn test_error_codes_match_the_specification() {
        assert_eq!(Error::NotInitialized as u32, 1);
        assert_eq!(Error::AlreadyInitialized as u32, 2);
        assert_eq!(Error::HashAlreadyAnchored as u32, 3);
        assert_eq!(Error::HashNotFound as u32, 4);
        assert_eq!(Error::Unauthorized as u32, 5);
        assert_eq!(Error::RootAlreadyAnchored as u32, 6);
        assert_eq!(Error::RootNotFound as u32, 7);
        assert_eq!(Error::EmptyBatch as u32, 8);
    }

    // ── Merkle root batching ──────────────────────────────────────

    /// Build a two-leaf tree and return (root, leaf_a, leaf_b).
    fn two_leaf_tree(env: &Env) -> (BytesN<32>, BytesN<32>, BytesN<32>) {
        let a = make_hash(env, &[1u8; 32]);
        let b = make_hash(env, &[2u8; 32]);
        let leaf_a = crate::merkle::hash_leaf(env, &a);
        let leaf_b = crate::merkle::hash_leaf(env, &b);
        let root = crate::merkle::hash_node(env, &leaf_a, &leaf_b);
        (root, a, b)
    }

    #[test]
    fn test_anchor_root_and_get_root() {
        let env = Env::default();
        let (_, client) = setup_env(&env);
        let admin = Address::generate(&env);
        client.initialize(&admin);
        let submitter = Address::generate(&env);
        let (root, _, _) = two_leaf_tree(&env);

        let record = client.anchor_root(&submitter, &root, &2);

        assert_eq!(record.merkle_root, root);
        assert_eq!(record.leaf_count, 2);
        assert_eq!(record.submitter, submitter);

        let stored = client.get_root(&root);
        assert!(stored.is_some());
        assert_eq!(stored.unwrap().leaf_count, 2);

        let unknown = make_hash(&env, &[99u8; 32]);
        assert!(client.get_root(&unknown).is_none());
    }

    #[test]
    fn test_anchor_root_rejects_empty_batch() {
        let env = Env::default();
        let (_, client) = setup_env(&env);
        let admin = Address::generate(&env);
        client.initialize(&admin);
        let submitter = Address::generate(&env);
        let (root, _, _) = two_leaf_tree(&env);

        let err = client.try_anchor_root(&submitter, &root, &0).unwrap_err();
        assert_eq!(err.unwrap(), Error::EmptyBatch);
    }

    #[test]
    fn test_no_double_anchor_root() {
        let env = Env::default();
        let (_, client) = setup_env(&env);
        let admin = Address::generate(&env);
        client.initialize(&admin);
        let submitter = Address::generate(&env);
        let (root, _, _) = two_leaf_tree(&env);

        client.anchor_root(&submitter, &root, &2);

        let err = client.try_anchor_root(&submitter, &root, &2).unwrap_err();
        assert_eq!(err.unwrap(), Error::RootAlreadyAnchored);
    }

    #[test]
    fn test_batch_calls_require_initialization() {
        let env = Env::default();
        // Registered without initializing and without mocked auths, so a genuine
        // auth failure cannot be mistaken for the missing-admin error.
        let contract_id = env.register(crate::GeoGuardLedger, ());
        let client = GeoGuardLedgerClient::new(&env, &contract_id);
        let who = Address::generate(&env);
        let root = make_hash(&env, &[5u8; 32]);

        assert_eq!(
            client
                .try_anchor_root(&who, &root, &1)
                .unwrap_err()
                .unwrap(),
            Error::NotInitialized
        );
        assert_eq!(
            client
                .try_extend_root_ttl(&root, &500_000)
                .unwrap_err()
                .unwrap(),
            Error::NotInitialized
        );
    }

    #[test]
    fn test_verify_inclusion_two_leaves() {
        let env = Env::default();
        let (_, client) = setup_env(&env);
        let admin = Address::generate(&env);
        client.initialize(&admin);
        let submitter = Address::generate(&env);
        let (root, hash_a, hash_b) = two_leaf_tree(&env);
        let leaf_a = crate::merkle::hash_leaf(&env, &hash_a);
        let leaf_b = crate::merkle::hash_leaf(&env, &hash_b);

        client.anchor_root(&submitter, &root, &2);

        // Left leaf proves with the right leaf as its sibling.
        assert!(client.verify_inclusion(&root, &hash_a, &0, &vec![&env, leaf_b.clone()]));
        // Right leaf proves with the left leaf as its sibling.
        assert!(client.verify_inclusion(&root, &hash_b, &1, &vec![&env, leaf_a.clone()]));
    }

    #[test]
    fn test_verify_inclusion_rejects_wrong_proof() {
        let env = Env::default();
        let (_, client) = setup_env(&env);
        let admin = Address::generate(&env);
        client.initialize(&admin);
        let submitter = Address::generate(&env);
        let (root, hash_a, hash_b) = two_leaf_tree(&env);
        let leaf_a = crate::merkle::hash_leaf(&env, &hash_a);
        let leaf_b = crate::merkle::hash_leaf(&env, &hash_b);
        // A dataset that was never part of the batch.
        let outsider = make_hash(&env, &[7u8; 32]);

        client.anchor_root(&submitter, &root, &2);

        // Correct leaf but the index/side is wrong.
        assert!(!client.verify_inclusion(&root, &hash_a, &1, &vec![&env, leaf_a.clone()]));
        // Leaf that is not in the batch.
        assert!(!client.verify_inclusion(&root, &outsider, &0, &vec![&env, leaf_b.clone()]));
    }

    #[test]
    fn test_verify_inclusion_single_leaf() {
        let env = Env::default();
        let (_, client) = setup_env(&env);
        let admin = Address::generate(&env);
        client.initialize(&admin);
        let submitter = Address::generate(&env);
        let hash = make_hash(&env, &[3u8; 32]);
        // A one-leaf tree's root is that leaf's hash and its proof is empty.
        let root = crate::merkle::hash_leaf(&env, &hash);

        client.anchor_root(&submitter, &root, &1);

        assert!(client.verify_inclusion(&root, &hash, &0, &vec![&env]));
    }

    #[test]
    fn test_verify_inclusion_odd_level_duplicates_last() {
        let env = Env::default();
        let (_, client) = setup_env(&env);
        let admin = Address::generate(&env);
        client.initialize(&admin);
        let submitter = Address::generate(&env);

        let hash_a = make_hash(&env, &[1u8; 32]);
        let hash_b = make_hash(&env, &[2u8; 32]);
        let hash_c = make_hash(&env, &[3u8; 32]);
        let l0 = crate::merkle::hash_leaf(&env, &hash_a);
        let l1 = crate::merkle::hash_leaf(&env, &hash_b);
        let l2 = crate::merkle::hash_leaf(&env, &hash_c);
        // Odd level: the trailing node is paired with itself.
        let n01 = crate::merkle::hash_node(&env, &l0, &l1);
        let n22 = crate::merkle::hash_node(&env, &l2, &l2);
        let root = crate::merkle::hash_node(&env, &n01, &n22);

        client.anchor_root(&submitter, &root, &3);

        // Trailing leaf's proof repeats it at the first level.
        assert!(client.verify_inclusion(&root, &hash_c, &2, &vec![&env, l2.clone(), n01.clone()]));
        // Leading leaf uses the duplicated subtree above it.
        assert!(client.verify_inclusion(&root, &hash_a, &0, &vec![&env, l1.clone(), n22.clone()]));
    }

    #[test]
    fn test_verify_inclusion_unanchored_root_is_false() {
        let env = Env::default();
        let (_, client) = setup_env(&env);
        let admin = Address::generate(&env);
        client.initialize(&admin);
        let (root, hash_a, hash_b) = two_leaf_tree(&env);
        let leaf_b = crate::merkle::hash_leaf(&env, &hash_b);

        // The same proof is rejected while the root was never anchored.
        assert!(!client.verify_inclusion(&root, &hash_a, &0, &vec![&env, leaf_b]));
    }

    #[test]
    fn test_batch_counts() {
        let env = Env::default();
        let (_, client) = setup_env(&env);
        let admin = Address::generate(&env);
        client.initialize(&admin);
        let submitter = Address::generate(&env);

        assert_eq!(client.get_batch_count(&submitter), 0);
        assert_eq!(client.get_total_batches(), 0);

        let root_a = crate::merkle::hash_node(
            &env,
            &make_hash(&env, &[1u8; 32]),
            &make_hash(&env, &[2u8; 32]),
        );
        client.anchor_root(&submitter, &root_a, &10);
        assert_eq!(client.get_batch_count(&submitter), 1);

        let root_b = crate::merkle::hash_node(
            &env,
            &make_hash(&env, &[3u8; 32]),
            &make_hash(&env, &[4u8; 32]),
        );
        client.anchor_root(&submitter, &root_b, &20);
        assert_eq!(client.get_batch_count(&submitter), 2);
        assert_eq!(client.get_total_batches(), 2);

        // Root batches are counted separately from single-hash anchors.
        assert_eq!(client.get_total_anchored(), 0);
    }

    #[test]
    fn test_extend_root_ttl_renews_to_the_requested_target() {
        let env = Env::default();
        let (contract_id, client) = setup_env(&env);
        let admin = Address::generate(&env);
        client.initialize(&admin);
        let submitter = Address::generate(&env);
        let (root, _, _) = two_leaf_tree(&env);

        client.anchor_root(&submitter, &root, &2);
        // Ask for a target above the write-time bump so the renewal takes effect.
        client.extend_root_ttl(&root, &4_000_000);

        assert_eq!(root_ttl(&env, &contract_id, &root), 4_000_000);
    }

    #[test]
    fn test_extend_root_ttl_is_a_noop_while_the_root_is_well_covered() {
        let env = Env::default();
        let (contract_id, client) = setup_env(&env);
        let admin = Address::generate(&env);
        client.initialize(&admin);
        let submitter = Address::generate(&env);
        let (root, _, _) = two_leaf_tree(&env);

        client.anchor_root(&submitter, &root, &2);
        let after_write = root_ttl(&env, &contract_id, &root);

        // The write-time bump already covers the root well past this target, so
        // the renewal must leave the entry alone.
        client.extend_root_ttl(&root, &(after_write + 10_000));

        assert_eq!(root_ttl(&env, &contract_id, &root), after_write);
    }

    #[test]
    fn test_extend_root_ttl_nonexistent() {
        let env = Env::default();
        let (_, client) = setup_env(&env);
        let admin = Address::generate(&env);
        client.initialize(&admin);
        let unknown = make_hash(&env, &[99u8; 32]);

        let err = client.try_extend_root_ttl(&unknown, &500_000).unwrap_err();
        assert_eq!(err.unwrap(), Error::RootNotFound);
    }

    #[test]
    fn test_initialize_resets_batch_counter() {
        let env = Env::default();
        let (_, client) = setup_env(&env);
        let admin = Address::generate(&env);
        client.initialize(&admin);

        assert_eq!(client.get_total_batches(), 0);
    }
}
