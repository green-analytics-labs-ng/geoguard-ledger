//! Merkle hashing helpers shared by root anchoring and inclusion proofs.
//!
//! The tree layout is fully specified so that independent verifiers can
//! reproduce it from the published rules:
//!
//! - Leaf:     `SHA256(0x00 || dataset_hash)`
//! - Internal: `SHA256(0x01 || left || right)`
//! - A level with an odd number of nodes pairs its final node with itself.
//!
//! The `0x00` / `0x01` prefixes domain-separate leaves from internal nodes so a
//! 32-byte dataset hash can never be reinterpreted as an interior node.
//!
//! The off-chain implementation in `backend/app/services/merkle.py` mirrors
//! these rules byte for byte; `tests/test_merkle.py` cross-checks the two.

use soroban_sdk::{Bytes, BytesN, Env};

/// Domain separator prefix for leaf hashes.
const LEAF_PREFIX: u8 = 0x00;

/// Domain separator prefix for internal node hashes.
const NODE_PREFIX: u8 = 0x01;

/// Hash a dataset hash into a Merkle leaf.
pub fn hash_leaf(env: &Env, dataset_hash: &BytesN<32>) -> BytesN<32> {
    let mut payload = [0u8; 33];
    payload[0] = LEAF_PREFIX;
    payload[1..].copy_from_slice(&dataset_hash.to_array());
    env.crypto()
        .sha256(&Bytes::from_array(env, &payload))
        .to_bytes()
}

/// Hash two child nodes into their parent.
pub fn hash_node(env: &Env, left: &BytesN<32>, right: &BytesN<32>) -> BytesN<32> {
    let mut payload = [0u8; 65];
    payload[0] = NODE_PREFIX;
    payload[1..33].copy_from_slice(&left.to_array());
    payload[33..].copy_from_slice(&right.to_array());
    env.crypto()
        .sha256(&Bytes::from_array(env, &payload))
        .to_bytes()
}
