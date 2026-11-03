use soroban_sdk::{contractevent, contracttype, Address, BytesN, Symbol};

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

/// Emitted when a dataset hash is anchored.
///
/// `topics` and `data_format` are both stated explicitly rather than left to the
/// macro's defaults, because the defaults are not what this contract used to
/// publish: the topic prefix would become the struct name in snake_case
/// (`anchored`, not `Anchored`), and the data would become a map instead of a
/// tuple. Since `env.events().publish` was replaced here only because sdk 28
/// deprecates it, an off-chain consumer must see the event it saw before — same
/// topic symbol, same positional data — so both defaults are overridden.
#[contractevent(topics = ["Anchored"], data_format = "vec")]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Anchored {
    pub dataset_hash: BytesN<32>,
    pub submitter: Address,
    pub timestamp: u64,
}

/// Emitted when a Merkle root is anchored. Same explicit topic and data encoding
/// as [`Anchored`], for the same reason.
#[contractevent(topics = ["RootAnchored"], data_format = "vec")]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct RootAnchored {
    pub merkle_root: BytesN<32>,
    pub submitter: Address,
    pub leaf_count: u32,
    pub timestamp: u64,
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
