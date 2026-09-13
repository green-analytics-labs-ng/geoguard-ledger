#![no_std]
use soroban_sdk::{contract, contractimpl, Address, BytesN, Env, Symbol, Vec};

mod errors;
mod merkle;
mod storage;
mod types;

pub use errors::Error;
pub use types::{AnchorRecord, RootRecord};

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

/// Deepest sibling path `verify_inclusion` will walk.
///
/// `index` is a `u32`, so a leaf position needs at most 32 halvings to reach the
/// root: a longer path cannot describe a real position in any batch. Rejecting
/// it outright keeps a malformed call from burning budget on an arbitrarily
/// long path, and never turns away a proof that could have been genuine.
const MAX_PROOF_DEPTH: u32 = 32;

/// The threshold at which a renewal actually takes effect.
///
/// Keeps the threshold strictly below the target so the renewal decision and the
/// target are never the same value. The `max(1).min(extend_to)` clamp keeps the
/// threshold sane for very small targets and cannot underflow.
fn renewal_threshold(extend_to: u32) -> u32 {
    extend_to
        .saturating_sub(TTL_RENEWAL_MARGIN)
        .max(1)
        .min(extend_to)
}

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
        storage::set_total_batches(&env, 0);
        Ok(())
    }

    /// Anchor a dataset hash on-chain. Requires authorization from the submitter.
    ///
    /// The new record's TTL is pushed out to its full budget on write. A record
    /// is written once and never modified, so without that bump it would keep
    /// only the network's minimum persistent-entry TTL and be archived within
    /// days, taking [`verify_integrity`](Self::verify_integrity) with it.
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
        storage::bump_record_ttl(&env, &dataset_hash);
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

        let key = storage::DataKey::Record(dataset_hash);
        env.storage()
            .persistent()
            .extend_ttl(&key, renewal_threshold(extend_to), extend_to);

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

    // ── Merkle Root Batching ─────────────────────────────────────

    /// Anchor a Merkle root committing to a batch of dataset hashes.
    ///
    /// One root costs one Persistent entry and one TTL obligation regardless of
    /// how many datasets it commits to, which keeps anchoring cost flat as the
    /// number of submissions grows. Requires authorization from the submitter.
    ///
    /// Returns [`Error::NotInitialized`] if the contract has not been
    /// initialized, [`Error::EmptyBatch`] if `leaf_count` is zero (an empty batch
    /// commits to nothing), and [`Error::RootAlreadyAnchored`] if the root
    /// already exists.
    pub fn anchor_root(
        env: Env,
        submitter: Address,
        merkle_root: BytesN<32>,
        leaf_count: u32,
    ) -> Result<RootRecord, Error> {
        if !storage::has_admin(&env) {
            return Err(Error::NotInitialized);
        }

        submitter.require_auth();

        if leaf_count == 0 {
            return Err(Error::EmptyBatch);
        }
        if storage::has_root(&env, &merkle_root) {
            return Err(Error::RootAlreadyAnchored);
        }

        let timestamp = env.ledger().timestamp();
        let record = RootRecord {
            merkle_root: merkle_root.clone(),
            leaf_count,
            submitter: submitter.clone(),
            timestamp,
        };

        storage::set_root(&env, &merkle_root, &record);
        storage::bump_root_ttl(&env, &merkle_root);
        storage::increment_batch_count(&env, &submitter);
        storage::increment_total_batches(&env);

        env.events().publish(
            (Symbol::new(&env, "RootAnchored"),),
            (merkle_root, submitter, leaf_count, timestamp),
        );

        Ok(record)
    }

    /// Fetch the record for an anchored Merkle root. Read-only.
    pub fn get_root(env: Env, merkle_root: BytesN<32>) -> Option<RootRecord> {
        storage::get_root(&env, &merkle_root)
    }

    /// Verify that a dataset hash is included in an anchored Merkle batch.
    ///
    /// Recomputes the root from the leaf and the bottom-up `siblings` path and
    /// compares it against an anchored root. `index` is the leaf's position in
    /// the batch and is halved once per level. Read-only and no gas. Returns
    /// `false` when the root is not anchored or the proof does not reconstruct
    /// it, so callers can distinguish inclusion from a missing batch.
    pub fn verify_inclusion(
        env: Env,
        merkle_root: BytesN<32>,
        dataset_hash: BytesN<32>,
        index: u32,
        siblings: Vec<BytesN<32>>,
    ) -> bool {
        if !storage::has_root(&env, &merkle_root) {
            return false;
        }
        if siblings.len() > MAX_PROOF_DEPTH {
            return false;
        }

        let mut node = merkle::hash_leaf(&env, &dataset_hash);
        let mut idx = index;

        for sibling in siblings.iter() {
            node = if idx.is_multiple_of(2) {
                merkle::hash_node(&env, &node, &sibling)
            } else {
                merkle::hash_node(&env, &sibling, &node)
            };
            idx /= 2;
        }

        node == merkle_root
    }

    /// Number of Merkle roots anchored by a given submitter.
    pub fn get_batch_count(env: Env, submitter: Address) -> u32 {
        storage::get_batch_count(&env, &submitter)
    }

    /// Total number of Merkle roots anchored.
    pub fn get_total_batches(env: Env) -> u32 {
        storage::get_total_batches(&env)
    }

    /// Extend the TTL of an anchored Merkle root. Permissionless.
    ///
    /// A batch keeps thousands of datasets alive through one entry, so renewing
    /// that entry is what keeps an entire batch queryable. Uses the same renewal
    /// margin as `extend_ttl` so a call cannot silently no-op on a root that
    /// already sits near the target.
    ///
    /// Returns [`Error::NotInitialized`] or [`Error::RootNotFound`] as appropriate.
    pub fn extend_root_ttl(env: Env, merkle_root: BytesN<32>, extend_to: u32) -> Result<(), Error> {
        if !storage::has_admin(&env) {
            return Err(Error::NotInitialized);
        }
        if !storage::has_root(&env, &merkle_root) {
            return Err(Error::RootNotFound);
        }

        let key = storage::DataKey::Root(merkle_root);
        env.storage()
            .persistent()
            .extend_ttl(&key, renewal_threshold(extend_to), extend_to);

        Ok(())
    }
}

#[cfg(test)]
mod test;

#[cfg(test)]
mod test_properties;

#[cfg(test)]
mod test_support;
