#![no_std]
use soroban_sdk::{contract, contractimpl, Address, BytesN, Env, Symbol};

mod errors;
mod storage;
mod types;

pub use errors::Error;
pub use types::AnchorRecord;

/// How far below the requested `extend_to` target a record's remaining TTL must
/// fall before `extend_ttl` actually renews it.
///
/// The Soroban `extend_ttl(key, threshold, extend_to)` call only extends an entry
/// whose remaining TTL is *below* `threshold`. Passing `extend_to` as both
/// arguments (as this contract used to) leaves no headroom: a call made while the
/// entry already sits at or above the target silently does nothing. Renewing a
/// margin of ledgers early keeps records comfortably ahead of archival.
///
/// ~100,000 ledgers is roughly six days at Stellar's ~5s ledger close time.
const TTL_RENEWAL_MARGIN: u32 = 100_000;

#[contract]
pub struct GeoGuardLedger;

#[contractimpl]
impl GeoGuardLedger {
    /// Initialize the contract with an admin address. Called once at deployment.
    ///
    /// Returns [`Error::AlreadyInitialized`] if the contract already has an admin.
    pub fn initialize(env: Env, admin: Address) -> Result<(), Error> {
        if storage::has_admin(&env) {
            return Err(Error::AlreadyInitialized);
        }
        storage::set_admin(&env, &admin);
        storage::set_total_anchored(&env, 0);
        Ok(())
    }

    /// Anchor a dataset hash on-chain. Requires authorization from the submitter.
    ///
    /// Returns [`Error::NotInitialized`] if the contract has not been initialized
    /// and [`Error::HashAlreadyAnchored`] if the hash already exists.
    pub fn anchor_hash(
        env: Env,
        submitter: Address,
        dataset_hash: BytesN<32>,
        anomaly_score: u32,
        model_version: Symbol,
    ) -> Result<AnchorRecord, Error> {
        if !storage::has_admin(&env) {
            return Err(Error::NotInitialized);
        }

        submitter.require_auth();

        // Prevent overwriting existing records
        if storage::has_record(&env, &dataset_hash) {
            return Err(Error::HashAlreadyAnchored);
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

        Ok(record)
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
    ///
    /// The entry is renewed only once its remaining TTL drops below
    /// `extend_to - TTL_RENEWAL_MARGIN`, so the call reliably keeps records far
    /// from expiry instead of no-op'ing on an entry that already sits near the
    /// target.
    ///
    /// Returns [`Error::NotInitialized`] or [`Error::HashNotFound`] as appropriate.
    pub fn extend_ttl(env: Env, dataset_hash: BytesN<32>, extend_to: u32) -> Result<(), Error> {
        if !storage::has_admin(&env) {
            return Err(Error::NotInitialized);
        }
        if !storage::has_record(&env, &dataset_hash) {
            return Err(Error::HashNotFound);
        }

        // Keep the threshold strictly below the target so the renewal decision
        // and the target are never the same value. The `max(1).min(extend_to)`
        // clamp keeps the threshold sane for very small targets and cannot
        // underflow.
        let threshold = extend_to
            .saturating_sub(TTL_RENEWAL_MARGIN)
            .max(1)
            .min(extend_to);

        let key = storage::DataKey::Record(dataset_hash);
        env.storage()
            .persistent()
            .extend_ttl(&key, threshold, extend_to);

        Ok(())
    }

    /// Transfer admin rights to a new address. Admin only.
    ///
    /// `require_auth` enforces that the current admin authorized the call; an
    /// unauthorized caller aborts with the host's auth error. The
    /// [`Error::Unauthorized`] code documents that failure for clients.
    ///
    /// Returns [`Error::NotInitialized`] if the contract has no admin.
    pub fn transfer_admin(env: Env, new_admin: Address) -> Result<(), Error> {
        let admin = storage::get_admin(&env).ok_or(Error::NotInitialized)?;
        admin.require_auth();
        storage::set_admin(&env, &new_admin);
        Ok(())
    }
}

#[cfg(test)]
mod test;
