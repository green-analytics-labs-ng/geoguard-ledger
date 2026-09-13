//! Helpers shared by the property-based and gas-cost test modules.
//!
//! Kept separate so neither module has to reach into the other, and so the
//! tree builder that mirrors `merkle.rs` exists in exactly one place.

use soroban_sdk::{
    testutils::{storage::Persistent as _, EnvTestConfig},
    Address, BytesN, Env, Vec,
};

use crate::storage::DataKey;
use crate::GeoGuardLedgerClient;

/// An `Env` that does not write a `test_snapshots/*.json` file when it drops.
///
/// `test.rs` keeps the default capture so its snapshots stay committed and
/// reviewable. The property and gas modules deliberately opt out: a property
/// test builds one `Env` per generated case, so the default would scatter
/// hundreds of snapshot files across a single `cargo test`, none of them
/// carrying ledger state worth pinning.
pub fn quiet_env() -> Env {
    let mut env = Env::default();
    env.set_config(EnvTestConfig {
        capture_snapshot_at_drop: false,
    });
    env
}

pub fn setup(env: &Env) -> (Address, GeoGuardLedgerClient<'_>) {
    env.mock_all_auths();
    let contract_id = env.register(crate::GeoGuardLedger, ());
    let client = GeoGuardLedgerClient::new(env, &contract_id);
    (contract_id, client)
}

/// Remaining TTL (in ledgers) of a stored anchor record.
pub fn record_ttl(env: &Env, contract_id: &Address, hash: &BytesN<32>) -> u32 {
    env.as_contract(contract_id, || {
        env.storage()
            .persistent()
            .get_ttl(&DataKey::Record(hash.clone()))
    })
}

/// Dataset hashes that are guaranteed distinct for indices `0..n`.
///
/// The first eight bytes encode the index, so two leaves cannot collide no
/// matter what the generator supplies for the rest.
pub fn distinct_hashes(env: &Env, base: &[u8; 32], n: u32) -> Vec<BytesN<32>> {
    let mut hashes = Vec::new(env);
    for i in 0..n {
        let mut bytes = *base;
        bytes[..8].copy_from_slice(&u64::from(i).to_be_bytes());
        hashes.push_back(BytesN::from_array(env, &bytes));
    }
    hashes
}

/// A dataset hash that is not one of `distinct_hashes(.., n)` for any sane `n`:
/// its index field is the maximum `u64`, which the loop above never produces.
pub fn outsider_hash(env: &Env, base: &[u8; 32]) -> BytesN<32> {
    let mut bytes = *base;
    bytes[..8].copy_from_slice(&u64::MAX.to_be_bytes());
    BytesN::from_array(env, &bytes)
}

/// Flip a byte so the result is guaranteed to differ from the input.
pub fn tamper(env: &Env, hash: &BytesN<32>) -> BytesN<32> {
    let mut bytes = hash.to_array();
    bytes[0] ^= 0xFF;
    BytesN::from_array(env, &bytes)
}

/// A Merkle tree built with the contract's own hashing rules, so the proofs
/// these tests generate match the shape the backend produces.
///
/// Levels are stored bottom-up. An odd level pairs its trailing node with
/// itself, mirroring `merkle.rs`.
pub struct Tree {
    levels: Vec<Vec<BytesN<32>>>,
}

impl Tree {
    pub fn build(env: &Env, dataset_hashes: &Vec<BytesN<32>>) -> Self {
        let mut leaves = Vec::new(env);
        for hash in dataset_hashes.iter() {
            leaves.push_back(crate::merkle::hash_leaf(env, &hash));
        }

        let mut levels = Vec::new(env);
        levels.push_back(leaves.clone());

        let mut current = leaves;
        while current.len() > 1 {
            let mut next = Vec::new(env);
            let mut i = 0;
            while i < current.len() {
                let left = current.get(i).unwrap();
                let right = current.get(i + 1).unwrap_or_else(|| left.clone());
                next.push_back(crate::merkle::hash_node(env, &left, &right));
                i += 2;
            }
            levels.push_back(next.clone());
            current = next;
        }

        Self { levels }
    }

    pub fn root(&self) -> BytesN<32> {
        self.levels
            .get(self.levels.len() - 1)
            .unwrap()
            .get(0)
            .unwrap()
    }

    /// Sibling path for `index`, bottom-up.
    pub fn proof(&self, env: &Env, index: u32) -> Vec<BytesN<32>> {
        let mut siblings = Vec::new(env);
        let mut idx = index;
        let depth = self.levels.len() - 1;
        let mut level = 0;
        while level < depth {
            let nodes = self.levels.get(level).unwrap();
            let sibling_idx = if idx.is_multiple_of(2) {
                idx + 1
            } else {
                idx - 1
            };
            let sibling = nodes
                .get(sibling_idx)
                .unwrap_or_else(|| nodes.get(idx).unwrap());
            siblings.push_back(sibling);
            idx /= 2;
            level += 1;
        }
        siblings
    }
}
