//! Differential fuzz harness for the contract's Merkle inclusion verifier.
//!
//! [`check`] turns a byte slice into one verification scenario and asserts that
//! the contract agrees with an independent, plain-Rust reference implementation
//! of the documented scheme. libFuzzer's coverage feedback drives the search;
//! the assertions are what turn a failing input into a finding.
//!
//! # Why differential
//!
//! The contract folds a proof with SHA-256 through the host crypto API, while
//! the reference below uses the `sha2` crate. A mistake in the preimage layout,
//! the sibling ordering, or the index halving shows up as a disagreement — and a
//! disagreement means the on-chain verifier and the documented scheme (which
//! `backend/app/services/merkle.py` also implements) have drifted apart.
//!
//! Non-vacuity is handled explicitly: a verifier that returned `false` for
//! everything would satisfy most of the differential checks, so every case also
//! anchors a real tree and requires a genuine proof to come back `true`.
//!
//! # Why one `Env` per case, and many variants per `Env`
//!
//! A fresh `Env` per case costs about 0.38ms all in — register, initialize,
//! anchor, and the verification calls — while a single `verify_inclusion` costs
//! about 0.015ms. So the setup happens once per case and the cheap part is
//! repeated [`VARIANTS`] times: roughly 3x the time of a single-check case for 18
//! verification calls instead of one, i.e. about 6x the verifications per second.
//!
//! Reusing one `Env` across cases to skip the setup was measured and rejected:
//! the host accumulates every registered instance and stored entry, so per-case
//! cost climbs from 3.2ms to over 10ms within 2,000 cases — an order of magnitude
//! slower than the flat 0.38ms of a fresh `Env` — while resident memory grows
//! about 20KB per case. A fresh `Env` keeps cost flat and memory bounded, and
//! keeps a case's outcome a function of its input alone, which is what makes a
//! reported crash reproducible.

use geoguard_ledger::{GeoGuardLedger, GeoGuardLedgerClient};
use sha2::{Digest, Sha256};
use soroban_sdk::{
    testutils::{Address as _, EnvTestConfig},
    Address, BytesN, Env, Vec as SdkVec,
};

/// Mirrors `MAX_PROOF_DEPTH` in the contract's `lib.rs`.
pub const MAX_PROOF_DEPTH: usize = 32;

/// Largest batch a generated case builds.
const MAX_LEAVES: u8 = 12;

/// Longest sibling list a generated case builds. Exceeds [`MAX_PROOF_DEPTH`] on
/// purpose, so the bound is fuzzed rather than avoided.
const MAX_SIBLINGS: u8 = 40;

/// Differential checks run per case. Each costs ~0.015ms against a ~17ms setup,
/// so this trades a small amount of input space per check for a large gain in
/// verifier executions per second.
const VARIANTS: usize = 16;

// ---------------------------------------------------------------------------
// Reference model of the documented scheme.
// ---------------------------------------------------------------------------

fn sha256(parts: &[&[u8]]) -> [u8; 32] {
    let mut hasher = Sha256::new();
    for part in parts {
        hasher.update(part);
    }
    hasher.finalize().into()
}

/// `SHA256(0x00 || dataset_hash)`
pub fn reference_hash_leaf(dataset_hash: &[u8; 32]) -> [u8; 32] {
    sha256(&[&[0x00], dataset_hash])
}

/// `SHA256(0x01 || left || right)`
pub fn reference_hash_node(left: &[u8; 32], right: &[u8; 32]) -> [u8; 32] {
    sha256(&[&[0x01], left, right])
}

/// The tree levels bottom-up; `levels[0]` holds the leaves.
///
/// A level with an odd number of nodes pairs its trailing node with itself,
/// mirroring both `merkle.rs` and the Python implementation.
pub fn build_levels(leaves: &[[u8; 32]]) -> Vec<Vec<[u8; 32]>> {
    let mut levels = vec![leaves.iter().map(reference_hash_leaf).collect::<Vec<_>>()];

    while levels[levels.len() - 1].len() > 1 {
        let current = &levels[levels.len() - 1];
        let mut next = Vec::with_capacity(current.len().div_ceil(2));
        let mut i = 0;
        while i < current.len() {
            let left = current[i];
            // A trailing odd node is paired with itself.
            let right = if i + 1 < current.len() {
                current[i + 1]
            } else {
                left
            };
            next.push(reference_hash_node(&left, &right));
            i += 2;
        }
        levels.push(next);
    }

    levels
}

/// The bottom-up sibling path for `index`. Empty for a single-leaf batch, whose
/// root is the leaf itself.
pub fn reference_proof(levels: &[Vec<[u8; 32]>], index: u32) -> Vec<[u8; 32]> {
    let mut proof = Vec::with_capacity(levels.len().saturating_sub(1));
    let mut idx = index as usize;

    for level in &levels[..levels.len() - 1] {
        // Beyond the end of an odd level the node is its own sibling.
        let sibling = if idx ^ 1 < level.len() { idx ^ 1 } else { idx };
        proof.push(level[sibling]);
        idx /= 2;
    }

    proof
}

/// Mirrors `verify_inclusion` minus the "root is anchored" precondition, which
/// is a storage lookup rather than Merkle logic.
///
/// Written from the documented scheme rather than from the contract's source, so
/// that it is able to disagree with the contract.
pub fn reference_verify(
    root: &[u8; 32],
    dataset_hash: &[u8; 32],
    index: u32,
    siblings: &[[u8; 32]],
) -> bool {
    if siblings.len() > MAX_PROOF_DEPTH {
        return false;
    }

    let mut node = reference_hash_leaf(dataset_hash);
    let mut idx = index;

    for sibling in siblings {
        node = if idx % 2 == 0 {
            reference_hash_node(&node, sibling)
        } else {
            reference_hash_node(sibling, &node)
        };
        idx /= 2;
    }

    node == *root
}

// ---------------------------------------------------------------------------
// Input derivation.
// ---------------------------------------------------------------------------

/// Reads bytes without requiring a particular length. Values wrap, so every
/// input — including the empty one — yields a valid case.
///
/// Fields are read in sequence rather than derived from a hash of the whole
/// input, so a one-byte mutation perturbs one field: that is what lets libFuzzer
/// hill-climb instead of scrambling the entire scenario.
struct Reader<'a> {
    data: &'a [u8],
    pos: usize,
}

impl<'a> Reader<'a> {
    fn new(data: &'a [u8]) -> Self {
        Self { data, pos: 0 }
    }

    fn u8(&mut self) -> u8 {
        if self.data.is_empty() {
            return 0;
        }
        let byte = self.data[self.pos % self.data.len()];
        self.pos += 1;
        byte
    }

    fn u32(&mut self) -> u32 {
        let mut value = 0u32;
        for _ in 0..4 {
            value = (value << 8) | u32::from(self.u8());
        }
        value
    }

    fn take32(&mut self) -> [u8; 32] {
        let mut out = [0u8; 32];
        for byte in out.iter_mut() {
            *byte = self.u8();
        }
        out
    }

    /// A `[0, max]`-bounded sibling count plus the siblings themselves.
    fn siblings(&mut self, buffer: &mut [[u8; 32]; MAX_SIBLINGS as usize]) -> usize {
        let count = usize::from(self.u8() % MAX_SIBLINGS);
        for sibling in buffer.iter_mut().take(count) {
            *sibling = self.take32();
        }
        count
    }
}

// ---------------------------------------------------------------------------
// The case.
// ---------------------------------------------------------------------------

fn to_sdk(env: &Env, bytes: &[u8; 32]) -> BytesN<32> {
    BytesN::from_array(env, bytes)
}

fn to_sdk_proof(env: &Env, siblings: &[[u8; 32]]) -> SdkVec<BytesN<32>> {
    let mut out = SdkVec::new(env);
    for sibling in siblings {
        out.push_back(BytesN::from_array(env, sibling));
    }
    out
}

fn hex(bytes: &[u8]) -> String {
    let mut out = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        out.push_str(&format!("{byte:02x}"));
    }
    out
}

fn describe(root: &[u8; 32], dataset_hash: &[u8; 32], index: u32, siblings: &[[u8; 32]]) -> String {
    format!(
        "  root         {}\n  dataset_hash {}\n  index        {index}\n  siblings     {} entries",
        hex(root),
        hex(dataset_hash),
        siblings.len(),
    )
}

/// Run one fuzz case. Panics on any disagreement, which is what libFuzzer
/// reports as a finding.
pub fn check(data: &[u8]) {
    let mut reader = Reader::new(data);

    let leaf_count = 1 + u32::from(reader.u8() % MAX_LEAVES);

    let mut leaf_buffer = [[0u8; 32]; MAX_LEAVES as usize];
    for leaf in leaf_buffer.iter_mut().take(leaf_count as usize) {
        *leaf = reader.take32();
    }
    let leaves = &leaf_buffer[..leaf_count as usize];

    let genuine_index = reader.u32() % leaf_count;
    let levels = build_levels(leaves);
    let genuine_root = levels[levels.len() - 1][0];
    let genuine_leaf = leaves[genuine_index as usize];
    let genuine_siblings = reference_proof(&levels, genuine_index);

    let mut env = Env::default();
    env.mock_all_auths();
    // The SDK writes a `test_snapshots/*.json` file every time an `Env` is
    // dropped, which is a reasonable default for a test suite and completely
    // wrong here: at a few hundred cases per second this litters tens of
    // thousands of files per run (and 76MB was measured before this was set).
    env.set_config(EnvTestConfig {
        capture_snapshot_at_drop: false,
    });
    let contract_id = env.register(GeoGuardLedger, ());
    let client = GeoGuardLedgerClient::new(&env, &contract_id);
    let admin = Address::generate(&env);
    client.initialize(&admin);
    let submitter = Address::generate(&env);
    client.anchor_root(&submitter, &to_sdk(&env, &genuine_root), &leaf_count);

    let root = to_sdk(&env, &genuine_root);

    // (A) Completeness. A genuine proof must verify. Without this, every check
    // below would also be satisfied by a verifier that always returned false.
    let verified = client.verify_inclusion(
        &root,
        &to_sdk(&env, &genuine_leaf),
        &genuine_index,
        &to_sdk_proof(&env, &genuine_siblings),
    );
    assert!(
        verified,
        "the contract rejected a genuine inclusion proof\n  leaf_count    {leaf_count}\n  \
         genuine_index {genuine_index}\n  proof length  {}\n  leaf          {}\n  root          {}",
        genuine_siblings.len(),
        hex(&genuine_leaf),
        hex(&genuine_root),
    );

    // (B) Differential. Arbitrary dataset hashes, indices and proofs, against an
    // anchored root, compared with the reference. This is where the folding
    // logic, the sibling ordering and the depth bound are exercised.
    let mut sibling_buffer = [[0u8; 32]; MAX_SIBLINGS as usize];
    for variant in 0..VARIANTS {
        let dataset_hash = reader.take32();
        let index = reader.u32();
        let count = reader.siblings(&mut sibling_buffer);
        let siblings = &sibling_buffer[..count];

        let expected = reference_verify(&genuine_root, &dataset_hash, index, siblings);
        let actual = client.verify_inclusion(
            &root,
            &to_sdk(&env, &dataset_hash),
            &index,
            &to_sdk_proof(&env, siblings),
        );

        assert_eq!(
            actual, expected,
            "contract and reference disagree on variant {variant} (expected {expected}, got \
             {actual})\n{}",
            describe(&genuine_root, &dataset_hash, index, siblings),
        );
    }

    // (C) A root that was never anchored must never verify, however well formed
    // the proof is.
    let mut unanchored = reader.take32();
    while unanchored == genuine_root {
        unanchored[0] ^= 0x5a;
    }
    let dataset_hash = reader.take32();
    let index = reader.u32();
    let count = reader.siblings(&mut sibling_buffer);
    let siblings = &sibling_buffer[..count];

    let actual = client.verify_inclusion(
        &to_sdk(&env, &unanchored),
        &to_sdk(&env, &dataset_hash),
        &index,
        &to_sdk_proof(&env, siblings),
    );
    assert!(
        !actual,
        "an unanchored root verified\n{}",
        describe(&unanchored, &dataset_hash, index, siblings),
    );
}
