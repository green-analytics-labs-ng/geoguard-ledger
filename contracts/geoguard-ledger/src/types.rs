use soroban_sdk::{contracttype, Address, BytesN, Symbol};

/// Core record stored on-chain per dataset submission.
#[derive(Clone, Debug, PartialEq, Eq)]
#[contracttype]
pub struct AnchorRecord {
    pub dataset_hash: BytesN<32>,
    pub anomaly_score: u32,    // Fixed-point: 0–10000 (0.00–100.00%)
    pub model_version: Symbol,
    pub timestamp: u64,
    pub submitter: Address,
}
