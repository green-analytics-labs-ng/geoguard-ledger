use soroban_sdk::{contracttype, Address, BytesN, Env};

use crate::types::AnchorRecord;

// ─── Storage Keys (idiomatic Soroban DataKey enum) ───────────────

#[derive(Clone, Debug, PartialEq, Eq)]
#[contracttype]
pub enum DataKey {
    Admin,
    TotalAnchored,
    Record(BytesN<32>),
    SubCount(Address),
}

// ─── Admin ───────────────────────────────────────────────────────

pub fn has_admin(env: &Env) -> bool {
    env.storage().instance().has(&DataKey::Admin)
}

pub fn get_admin(env: &Env) -> Address {
    env.storage().instance().get(&DataKey::Admin).unwrap()
}

pub fn set_admin(env: &Env, admin: &Address) {
    env.storage().instance().set(&DataKey::Admin, admin);
}

// ─── Anchor Records (Persistent) ─────────────────────────────────

pub fn has_record(env: &Env, hash: &BytesN<32>) -> bool {
    env.storage().persistent().has(&DataKey::Record(hash.clone()))
}

pub fn get_record(env: &Env, hash: &BytesN<32>) -> Option<AnchorRecord> {
    env.storage().persistent().get(&DataKey::Record(hash.clone()))
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
