"""IPFS / Arweave integration for decentralized raw data storage.

Phase 3: Implement when IPFS storage is introduced.
"""


async def upload_to_ipfs(data: bytes) -> str:
    """Upload raw CSV data to IPFS and return the CID."""
    # TODO: Implement IPFS upload (Phase 3)
    raise NotImplementedError("IPFS storage not yet implemented")


async def fetch_from_ipfs(cid: str) -> bytes:
    """Fetch raw CSV data from IPFS by CID."""
    # TODO: Implement IPFS fetch (Phase 3)
    raise NotImplementedError("IPFS storage not yet implemented")
