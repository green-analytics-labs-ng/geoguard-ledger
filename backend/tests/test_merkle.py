"""Unit tests for the Merkle batching service.

The tree layout is part of the on-chain interface, so these tests pin the exact
bytes it produces and cross-check the proof round trip for every leaf position.
"""

import hashlib

import pytest

from app.core.exceptions import MerkleError
from app.services import merkle

# Deterministic 32-byte dataset hashes used throughout.
HASH_1 = hashlib.sha256(b"dataset-1").hexdigest()
HASH_2 = hashlib.sha256(b"dataset-2").hexdigest()
HASH_3 = hashlib.sha256(b"dataset-3").hexdigest()
HASHES = [HASH_1, HASH_2, HASH_3]

# Golden values locking the wire format shared with the Soroban verifier.
# If these change, the on-chain verifier in contracts/geoguard-ledger/src/merkle.rs
# must change in lockstep or proofs generated here will be rejected.
ROOT_ONE_LEAF = "932cb9de2c38936f594bb55c8394d175e1a57915f8cd1d2dc59b0e7898e6d48a"
ROOT_TWO_LEAVES = "6e651f027bfc04962259b247b0e8e3b5fbccdf5de56385277d8a4cd3cb7cb02e"
ROOT_THREE_LEAVES = "80b9c40235df7436795887f1c0305690d613480913ce3f7210486045b1d649c8"
PROOF_TWO_LEAVES_FIRST = ["ef40cfffb02b6b1766cec8619db839d97eb2ab11e19a918d7e19496f52645f64"]
PROOF_THREE_LEAVES_LAST = [
    "5d36bf9d127fa6c274a717f9c441e334813bfdb81f785afd0cd515ce4b11ba20",
    "6e651f027bfc04962259b247b0e8e3b5fbccdf5de56385277d8a4cd3cb7cb02e",
]


# ── Primitives ────────────────────────────────────────────────────


def test_hash_leaf_is_domain_separated():
    """A leaf is SHA256(0x00 || dataset_hash), not a bare hash of the data."""
    raw = bytes.fromhex(HASH_1)
    assert merkle.hash_leaf(raw) == hashlib.sha256(b"\x00" + raw).digest()
    # A bare SHA256 of the same bytes must not be mistaken for a leaf.
    assert merkle.hash_leaf(raw) != hashlib.sha256(raw).digest()


def test_hash_node_is_domain_separated():
    """An internal node is SHA256(0x01 || left || right)."""
    left = merkle.hash_leaf(bytes.fromhex(HASH_1))
    right = merkle.hash_leaf(bytes.fromhex(HASH_2))
    assert merkle.hash_node(left, right) == hashlib.sha256(b"\x01" + left + right).digest()


def test_hash_node_is_order_sensitive():
    """Swapping children must change the parent."""
    left = merkle.hash_leaf(bytes.fromhex(HASH_1))
    right = merkle.hash_leaf(bytes.fromhex(HASH_2))
    assert merkle.hash_node(left, right) != merkle.hash_node(right, left)


def test_hash_leaf_rejects_wrong_length():
    with pytest.raises(MerkleError):
        merkle.hash_leaf(b"too short")


# ── Roots ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("hashes", "expected"),
    [
        ([HASH_1], ROOT_ONE_LEAF),
        ([HASH_1, HASH_2], ROOT_TWO_LEAVES),
        ([HASH_1, HASH_2, HASH_3], ROOT_THREE_LEAVES),
    ],
)
def test_compute_root_golden(hashes, expected):
    assert merkle.compute_root(hashes) == expected


def test_compute_root_rejects_empty_batch():
    with pytest.raises(MerkleError):
        merkle.compute_root([])


def test_compute_root_rejects_invalid_hex():
    with pytest.raises(MerkleError):
        merkle.compute_root(["not hex"])


def test_compute_root_rejects_wrong_length_hash():
    with pytest.raises(MerkleError):
        merkle.compute_root(["abcd"])


def test_leaf_order_changes_the_root():
    """Leaf order is committed to, so it must be pinned by the caller."""
    assert merkle.compute_root([HASH_1, HASH_2]) != merkle.compute_root([HASH_2, HASH_1])


# ── Proofs ────────────────────────────────────────────────────────


def test_generate_proof_golden_two_leaves():
    assert merkle.generate_proof([HASH_1, HASH_2], 0) == PROOF_TWO_LEAVES_FIRST


def test_single_leaf_proof_is_empty():
    assert merkle.generate_proof([HASH_1], 0) == []


def test_odd_level_trailing_leaf_repeats_itself():
    """With a trailing odd node, its first sibling is the node itself."""
    proof = merkle.generate_proof(HASHES, 2)
    assert proof == PROOF_THREE_LEAVES_LAST
    assert proof[0] == merkle.hash_leaf(bytes.fromhex(HASH_3)).hex()


@pytest.mark.parametrize("leaf_count", [1, 2, 3, 4, 5, 6, 7, 8, 9, 16])
def test_proof_round_trips_for_every_leaf(leaf_count):
    """Every leaf must produce a proof that reconstructs the batch root."""
    hashes = [hashlib.sha256(f"dataset-{i}".encode()).hexdigest() for i in range(leaf_count)]
    root = merkle.compute_root(hashes)

    for index, dataset_hash in enumerate(hashes):
        proof = merkle.generate_proof(hashes, index)
        assert len(proof) == merkle.proof_length(leaf_count)
        assert merkle.verify_proof(dataset_hash, index, proof, root)


def test_verify_proof_rejects_leaf_not_in_batch():
    hashes = [HASH_1, HASH_2, HASH_3]
    root = merkle.compute_root(hashes)
    proof = merkle.generate_proof(hashes, 0)
    outsider = hashlib.sha256(b"dataset-99").hexdigest()

    assert not merkle.verify_proof(outsider, 0, proof, root)


def test_verify_proof_rejects_wrong_index():
    hashes = [HASH_1, HASH_2]
    root = merkle.compute_root(hashes)
    assert not merkle.verify_proof(HASH_1, 1, PROOF_TWO_LEAVES_FIRST, root)


def test_verify_proof_rejects_tampered_proof():
    hashes = [HASH_1, HASH_2]
    root = merkle.compute_root(hashes)
    tampered = [hashlib.sha256(b"tampered").hexdigest()]
    assert not merkle.verify_proof(HASH_1, 0, tampered, root)


def test_generate_proof_rejects_out_of_range_index():
    with pytest.raises(MerkleError):
        merkle.generate_proof([HASH_1, HASH_2], 2)
    with pytest.raises(MerkleError):
        merkle.generate_proof([HASH_1, HASH_2], -1)


@pytest.mark.parametrize(
    ("leaf_count", "expected"),
    [(1, 0), (2, 1), (3, 2), (4, 2), (5, 3), (8, 3), (9, 4)],
)
def test_proof_length(leaf_count, expected):
    assert merkle.proof_length(leaf_count) == expected


def test_proof_length_rejects_empty_batch():
    with pytest.raises(MerkleError):
        merkle.proof_length(0)
