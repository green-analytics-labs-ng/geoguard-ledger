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

## 5. Frontend: Freighter Wallet vs. Custom Signing

- Freighter is the de facto standard for Stellar browser wallets.
- Using Freighter means the backend never sees private keys.
- Transaction signing happens client-side, reducing the attack surface.
