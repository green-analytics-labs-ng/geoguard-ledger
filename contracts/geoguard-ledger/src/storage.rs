use soroban_sdk::{contracttype, Address, BytesN, Env};

use crate::types::{AnchorRecord, RootRecord};

// ─── Storage Keys (idiomatic Soroban DataKey enum) ───────────────

#[derive(Clone, Debug, PartialEq, Eq)]
#[contracttype]
pub enum DataKey {
    Admin,
    TotalAnchored,
    Record(BytesN<32>),
    SubCount(Address),
    TotalBatches,
    BatchCount(Address),
    Root(BytesN<32>),
}

// ─── Root TTL Budgets ────────────────────────────────────────────
// Ledgers are ~5 seconds, so a day is ~17,280 ledgers.

/// Extend a root's TTL once fewer than ~30 days of rent remain.
const ROOT_TTL_THRESHOLD: u32 = 518_400;

/// TTL a root is extended to on write (~180 days).
const ROOT_TTL_EXTEND_TO: u32 = 3_110_400;

// ─── Admin ───────────────────────────────────────────────────────

pub fn has_admin(env: &Env) -> bool {
    env.storage().instance().has(&DataKey::Admin)
}

pub fn get_admin(env: &Env) -> Option<Address> {
    env.storage().instance().get(&DataKey::Admin)
}

pub fn set_admin(env: &Env, admin: &Address) {
    env.storage().instance().set(&DataKey::Admin, admin);
}

// ─── Anchor Records (Persistent) ─────────────────────────────────

pub fn has_record(env: &Env, hash: &BytesN<32>) -> bool {
    env.storage()
        .persistent()
        .has(&DataKey::Record(hash.clone()))
}

pub fn get_record(env: &Env, hash: &BytesN<32>) -> Option<AnchorRecord> {
    env.storage()
        .persistent()
        .get(&DataKey::Record(hash.clone()))
}

pub fn set_record(env: &Env, hash: &BytesN<32>, record: &AnchorRecord) {
    env.storage()
        .persistent()
        .set(&DataKey::Record(hash.clone()), record);
}

// ─── Submit Counters (Persistent) ────────────────────────────────

pub fn get_submit_count(env: &Env, submitter: &Address) -> u32 {
    env.storage()
        .persistent()
        .get(&DataKey::SubCount(submitter.clone()))
        .unwrap_or(0)
}

pub fn increment_submit_count(env: &Env, submitter: &Address) {
    let count = get_submit_count(env, submitter) + 1;
    env.storage()
        .persistent()
        .set(&DataKey::SubCount(submitter.clone()), &count);
}

// ─── Global Counter (Instance) ───────────────────────────────────

pub fn get_total_anchored(env: &Env) -> u32 {
    env.storage()
        .instance()
        .get(&DataKey::TotalAnchored)
        .unwrap_or(0)
}

pub fn set_total_anchored(env: &Env, count: u32) {
    env.storage()
        .instance()
        .set(&DataKey::TotalAnchored, &count);
}

pub fn increment_total_anchored(env: &Env) {
    let count = get_total_anchored(env) + 1;
    set_total_anchored(env, count);
}

// ─── Merkle Roots (Persistent) ───────────────────────────────────

pub fn has_root(env: &Env, root: &BytesN<32>) -> bool {
    env.storage().persistent().has(&DataKey::Root(root.clone()))
}

pub fn get_root(env: &Env, root: &BytesN<32>) -> Option<RootRecord> {
    env.storage().persistent().get(&DataKey::Root(root.clone()))
}

pub fn set_root(env: &Env, root: &BytesN<32>, record: &RootRecord) {
    env.storage()
        .persistent()
        .set(&DataKey::Root(root.clone()), record);
}

/// Push a freshly written root's TTL out to the full budget.
///
/// Batching exists so thousands of datasets share one Persistent entry and
/// therefore one rent obligation; renewing it proactively keeps the whole
/// batch queryable without archival-restoration overhead.
pub fn bump_root_ttl(env: &Env, root: &BytesN<32>) {
    let key = DataKey::Root(root.clone());
    env.storage()
        .persistent()
        .extend_ttl(&key, ROOT_TTL_THRESHOLD, ROOT_TTL_EXTEND_TO);
}

// ─── Batch Counters (Persistent) ─────────────────────────────────

pub fn get_batch_count(env: &Env, submitter: &Address) -> u32 {
    env.storage()
        .persistent()
        .get(&DataKey::BatchCount(submitter.clone()))
        .unwrap_or(0)
}

pub fn increment_batch_count(env: &Env, submitter: &Address) {
    let count = get_batch_count(env, submitter) + 1;
    env.storage()
        .persistent()
        .set(&DataKey::BatchCount(submitter.clone()), &count);
}

// ─── Global Batch Counter (Instance) ─────────────────────────────

pub fn get_total_batches(env: &Env) -> u32 {
    env.storage()
        .instance()
        .get(&DataKey::TotalBatches)
        .unwrap_or(0)
}

pub fn set_total_batches(env: &Env, count: u32) {
    env.storage().instance().set(&DataKey::TotalBatches, &count);
}

pub fn increment_total_batches(env: &Env) {
    let count = get_total_batches(env) + 1;
    set_total_batches(env, count);
}
