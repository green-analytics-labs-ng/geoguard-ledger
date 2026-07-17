#![no_std]
use soroban_sdk::{contract, contractimpl, Address, BytesN, Env, Symbol};

mod errors;
mod storage;
mod types;

pub use errors::Error;
pub use types::AnchorRecord;

#[contract]
pub struct GeoGuardLedger;

#[contractimpl]
impl GeoGuardLedger {
    /// Initialize the contract with an admin address. Called once at deployment.
    pub fn initialize(env: Env, admin: Address) {
        if storage::has_admin(&env) {
            panic!("Contract already initialized");
        }
        storage::set_admin(&env, &admin);
        storage::set_total_anchored(&env, 0);
    }

    /// Anchor a dataset hash on-chain. Requires authorization from the submitter.
    pub fn anchor_hash(
        env: Env,
        submitter: Address,
        dataset_hash: BytesN<32>,
        anomaly_score: u32,
        model_version: Symbol,
    ) -> AnchorRecord {
        submitter.require_auth();

        // Prevent overwriting existing records
        if storage::has_record(&env, &dataset_hash) {
            panic!("Dataset hash already anchored");
        }

        let timestamp = env.ledger().timestamp();
        let record = AnchorRecord {
            dataset_hash: dataset_hash.clone(),
            anomaly_score,
            model_version,
            timestamp,
            submitter: submitter.clone(),
        };

        storage::set_record(&env, &dataset_hash, &record);
        storage::increment_submit_count(&env, &submitter);
        storage::increment_total_anchored(&env);

        env.events().publish(
            (Symbol::new(&env, "Anchored"),),
            (dataset_hash, submitter, timestamp),
        );

        record
    }

    /// Verify a dataset hash exists on-chain. Read-only, no auth required.
    pub fn verify_integrity(env: Env, dataset_hash: BytesN<32>) -> Option<AnchorRecord> {
        storage::get_record(&env, &dataset_hash)
    }

    /// Get the number of datasets anchored by a given submitter.
    pub fn get_record_count(env: Env, submitter: Address) -> u32 {
        storage::get_submit_count(&env, &submitter)
    }

    /// Get the total number of datasets anchored.
    pub fn get_total_anchored(env: Env) -> u32 {
        storage::get_total_anchored(&env)
    }

    /// Extend the TTL of a Persistent storage entry. Permissionless.
    pub fn extend_ttl(env: Env, dataset_hash: BytesN<32>, extend_to: u32) {
        if !storage::has_record(&env, &dataset_hash) {
            panic!("Dataset hash not found");
        }
        let key = storage::DataKey::Record(dataset_hash.clone());
        let threshold = env.ledger().sequence();
        env.storage()
            .persistent()
            .extend_ttl(&key, threshold, extend_to);
    }

    /// Transfer admin rights to a new address. Admin only.
    pub fn transfer_admin(env: Env, new_admin: Address) {
        let admin = storage::get_admin(&env);
        admin.require_auth();
        storage::set_admin(&env, &new_admin);
    }
}

#[cfg(test)]
mod test;
