#[cfg(test)]
mod tests {
    use soroban_sdk::{testutils::Address as _, Address, BytesN, Env, Symbol};

    use crate::GeoGuardLedgerClient;

    fn make_hash(env: &Env, data: &[u8; 32]) -> BytesN<32> {
        BytesN::from_array(env, data)
    }

    fn setup_env(env: &Env) -> GeoGuardLedgerClient {
        env.mock_all_auths();
        let contract_id = env.register(crate::GeoGuardLedger, ());
        GeoGuardLedgerClient::new(env, &contract_id)
    }

    #[test]
    fn test_initialize() {
        let env = Env::default();
        let client = setup_env(&env);
        let admin = Address::generate(&env);
        client.initialize(&admin);
        assert_eq!(client.get_total_anchored(), 0);
    }

    #[test]
    #[should_panic(expected = "Contract already initialized")]
    fn test_initialize_twice() {
        let env = Env::default();
        let client = setup_env(&env);
        let admin = Address::generate(&env);
        client.initialize(&admin);
        client.initialize(&admin);
    }

    #[test]
    fn test_anchor_and_verify() {
        let env = Env::default();
        let client = setup_env(&env);
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
    #[should_panic(expected = "Dataset hash already anchored")]
    fn test_no_double_anchor() {
        let env = Env::default();
        let client = setup_env(&env);
        let admin = Address::generate(&env);
        client.initialize(&admin);
        let submitter = Address::generate(&env);
        let hash = make_hash(&env, &[1u8; 32]);

        client.anchor_hash(&submitter, &hash, &0, &Symbol::new(&env, "isoforest_v1"));
        client.anchor_hash(&submitter, &hash, &0, &Symbol::new(&env, "isoforest_v1"));
    }

    #[test]
    fn test_record_count() {
        let env = Env::default();
        let client = setup_env(&env);
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
    fn test_extend_ttl() {
        let env = Env::default();
        let client = setup_env(&env);
        let admin = Address::generate(&env);
        client.initialize(&admin);
        let submitter = Address::generate(&env);
        let hash = make_hash(&env, &[1u8; 32]);

        client.anchor_hash(&submitter, &hash, &0, &Symbol::new(&env, "v1"));
        client.extend_ttl(&hash, &(env.ledger().sequence() + 500_000));
    }

    #[test]
    #[should_panic(expected = "Dataset hash not found")]
    fn test_extend_ttl_nonexistent() {
        let env = Env::default();
        let client = setup_env(&env);
        let admin = Address::generate(&env);
        client.initialize(&admin);
        let hash = make_hash(&env, &[99u8; 32]);
        client.extend_ttl(&hash, &(env.ledger().sequence() + 500_000));
    }

    #[test]
    fn test_transfer_admin() {
        let env = Env::default();
        let client = setup_env(&env);
        let admin = Address::generate(&env);
        client.initialize(&admin);
        let new_admin = Address::generate(&env);

        client.transfer_admin(&new_admin);
    }

    #[test]
    #[should_panic(expected = "HostError")]
    fn test_transfer_admin_unauthorized() {
        let env = Env::default();
        // Intentionally do NOT call env.mock_all_auths() here — we want
        // admin.require_auth() inside transfer_admin to fail.
        let contract_id = env.register(crate::GeoGuardLedger, ());
        let client = GeoGuardLedgerClient::new(&env, &contract_id);

        let admin = Address::generate(&env);
        client.initialize(&admin);

        // Use a non-admin address to attempt the transfer.
        // The client auto-auths `imposter` as the Address arg, but the
        // contract calls admin.require_auth() — so it will fail.
        let imposter = Address::generate(&env);
        client.transfer_admin(&imposter);
    }
}
