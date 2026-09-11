#[cfg(test)]
mod tests {
    use soroban_sdk::{
        testutils::{storage::Persistent as _, Address as _, MockAuth, MockAuthInvoke},
        Address, BytesN, Env, IntoVal, Symbol,
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
    }
}
