# GeoGuard Ledger — Architecture Decisions

This document captures key architectural decisions and the rationale behind them.

## 1. Why Stellar / Soroban?

- **Low cost:** Transaction fees and state rent are orders of magnitude cheaper than Ethereum L1.
- **Academic-friendly:** No speculative token mechanics. XLM is a utility token for fees.
- **Soroban (Rust):** Rust's type system and borrow checker reduce smart contract bugs.
- **State rent model:** Unlike Ethereum's permanent storage, Stellar's rent model aligns incentives — stale data is naturally pruned unless someone pays to keep it alive.

## 2. Why SHA-256?

- Widely accepted, no known practical collisions.
- Natively supported in Soroban via `BytesN<32>`.
- Fast to compute in Python and JavaScript.

## 3. Why Isolation Forest for Anomaly Detection?

- Unsupervised — no labeled "fraudulent" data needed.
- Handles high-dimensional geochemical data well.
- Interpretable: per-row anomaly scores and feature contributions.
- Lightweight: can run synchronously in the API without a GPU.

## 4. Why Off-Chain Raw Data?

- Storing raw CSV data on-chain would be prohibitively expensive.
- Hashes provide tamper-evidence without exposing sensitive data.
- IPFS/Arweave provide decentralized storage for third-party verification.

## 5. Why Merkle Batching?

- **Cost scales with batches, not datasets.** Each on-chain `Record` is a Persistent ledger entry with its own rent. Anchoring a Merkle root stores one `RootRecord` for arbitrarily many datasets, so cost and rent stop growing with submission volume.
- **TTL renewal becomes tractable.** Roots expire like any Persistent entry, but renewing one root keeps an entire batch queryable instead of chasing thousands of records.
- **Verification stays independent.** An inclusion proof is checked by the contract itself (`verify_inclusion`), so a verifier does not need to trust the backend that produced the proof. The tree layout is published and implemented identically on-chain and off-chain.
- **Domain separation.** Leaves are `SHA256(0x00 || dataset_hash)` and interior nodes `SHA256(0x01 || left || right)`, so a dataset hash can never be reinterpreted as an interior node.

`anchor_hash` remains available for single datasets; batching is layered on top rather than replacing it.

## 6. Frontend: Freighter Wallet vs. Custom Signing

- Freighter is the de facto standard for Stellar browser wallets.
- Using Freighter means the backend never sees private keys.
- Transaction signing happens client-side, reducing the attack surface.
