"""Merkle tree construction and inclusion proofs for batch anchoring.

Anchoring one Merkle root instead of every dataset hash keeps the on-chain
storage cost flat: one Persistent entry (and one rent obligation) commits to an
arbitrary number of datasets.

The tree layout must reproduce the on-chain verifier in
``contracts/geoguard-ledger/src/merkle.rs`` byte for byte:

- leaf     : ``SHA256(0x00 || dataset_hash)``
- internal : ``SHA256(0x01 || left || right)``
- odd level: the final node is paired with itself (duplicated)

The ``0x00`` / ``0x01`` prefixes domain-separate leaves from interior nodes so a
dataset hash can never be reinterpreted as an internal node.

Ordering matters: leaves are committed in the order supplied by the caller, so
the caller must pin that order (a batch's ``leaf_index`` is only meaningful
relative to the batch that produced the root).
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from app.core.exceptions import MerkleError

LEAF_PREFIX = b"\x00"
NODE_PREFIX = b"\x01"
HASH_BYTES = 32


def hash_leaf(dataset_hash: bytes) -> bytes:
    """Hash a 32-byte dataset hash into a Merkle leaf."""
    if len(dataset_hash) != HASH_BYTES:
        raise MerkleError(f"dataset hash must be {HASH_BYTES} bytes, got {len(dataset_hash)}")

    return hashlib.sha256(LEAF_PREFIX + dataset_hash).digest()


def hash_node(left: bytes, right: bytes) -> bytes:
    """Hash two child nodes into their parent."""
    return hashlib.sha256(NODE_PREFIX + left + right).digest()


def _decode(hex_hash: str) -> bytes:
    """Decode a hex digest, rejecting anything that is not a 32-byte hash."""
    try:
        raw = bytes.fromhex(hex_hash)
    except ValueError as exc:
        raise MerkleError(f"invalid hex hash: {hex_hash!r}") from exc

    if len(raw) != HASH_BYTES:
        raise MerkleError(f"hash must be {HASH_BYTES} bytes, got {len(raw)}")

    return raw


def build_levels(leaf_hashes: Sequence[bytes]) -> list[list[bytes]]:
    """Return the tree levels bottom-up; ``levels[0]`` holds the leaf hashes.

    Raises:
        MerkleError: If no leaves are supplied.
    """
    if not leaf_hashes:
        raise MerkleError("cannot build a Merkle tree with no leaves")

    levels: list[list[bytes]] = [list(leaf_hashes)]

    while len(levels[-1]) > 1:
        current = levels[-1]
        parents: list[bytes] = []
        for i in range(0, len(current), 2):
            left = current[i]
            # A trailing odd node is paired with itself.
            right = current[i + 1] if i + 1 < len(current) else left
            parents.append(hash_node(left, right))
        levels.append(parents)

    return levels


def compute_root(dataset_hashes: Sequence[str]) -> str:
    """Compute the hex Merkle root over hex dataset hashes."""
    leaves = [hash_leaf(_decode(h)) for h in dataset_hashes]
    return build_levels(leaves)[-1][0].hex()


def proof_length(leaf_count: int) -> int:
    """Number of siblings in an inclusion proof for a batch of ``leaf_count``."""
    if leaf_count < 1:
        raise MerkleError("leaf count must be at least 1")

    length = 0
    size = leaf_count
    while size > 1:
        size = (size + 1) // 2
        length += 1
    return length


def generate_proof(dataset_hashes: Sequence[str], index: int) -> list[str]:
    """Generate the bottom-up sibling path for the leaf at ``index``.

    Returns hex-encoded siblings, one per level. An empty list means the batch
    has a single leaf, whose root is the leaf itself.
    """
    if index < 0 or index >= len(dataset_hashes):
        raise MerkleError(f"leaf index {index} is outside the batch (0..{len(dataset_hashes) - 1})")

    levels = build_levels([hash_leaf(_decode(h)) for h in dataset_hashes])

    proof: list[str] = []
    idx = index
    for level in levels[:-1]:
        sibling_index = idx ^ 1
        # Beyond the end of an odd level the node is its own sibling.
        if sibling_index >= len(level):
            sibling_index = idx
        proof.append(level[sibling_index].hex())
        idx //= 2

    return proof


def verify_proof(
    dataset_hash: str,
    index: int,
    proof: Sequence[str],
    root: str,
) -> bool:
    """Recompute the root from a leaf and proof and compare it to ``root``.

    This mirrors what the contract's ``verify_inclusion`` does, so a proof that
    passes here also passes on-chain. Useful for validating proofs before
    submitting a transaction, and for tests.
    """
    if index < 0:
        raise MerkleError("leaf index must not be negative")

    node = hash_leaf(_decode(dataset_hash))
    idx = index

    for sibling_hex in proof:
        sibling = _decode(sibling_hex)
        node = hash_node(node, sibling) if idx % 2 == 0 else hash_node(sibling, node)
        idx //= 2

    return node == _decode(root)
