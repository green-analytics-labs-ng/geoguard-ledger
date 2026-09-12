use soroban_sdk::{contracttype, Address, BytesN, Symbol};

/// Core record stored on-chain per dataset submission.
#[derive(Clone, Debug, PartialEq, Eq)]
#[contracttype]
pub struct AnchorRecord {
    pub dataset_hash: BytesN<32>,
    pub anomaly_score: u32, // Fixed-point: 0–10000 (0.00–100.00%)
    pub model_version: Symbol,
    pub timestamp: u64,
    pub submitter: Address,
}

/// Record stored on-chain for a Merkle root that commits to a batch of datasets.
///
/// Anchoring a root collapses the O(n) storage cost of individual anchors into
/// a single Persistent entry. A dataset is then verified with an
/// off-chain-generated inclusion proof checked against `merkle_root`.
#[derive(Clone, Debug, PartialEq, Eq)]
#[contracttype]
pub struct RootRecord {
    pub merkle_root: BytesN<32>,
    /// Number of dataset leaves committed to by this root.
    pub leaf_count: u32,
    pub submitter: Address,
    pub timestamp: u64,
}
