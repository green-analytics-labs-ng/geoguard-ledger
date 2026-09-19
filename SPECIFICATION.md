# GeoGuard Ledger — Specification

**Version:** 0.2.0  
**Author:** Green Analytics Labs  
**License:** Apache 2.0  
**Status:** Active — Implementation In Progress

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Data Flow](#3-data-flow)
4. [Smart Contract Logic (Soroban)](#4-smart-contract-logic-soroban)
5. [Backend API Specification (FastAPI)](#5-backend-api-specification-fastapi)
6. [Frontend Specification (React + TypeScript)](#6-frontend-specification-react--typescript)
7. [Repository Structure](#7-repository-structure)
8. [Testing Strategy](#8-testing-strategy)
9. [CI/CD Pipeline](#9-cicd-pipeline)
10. [Observability & Monitoring](#10-observability--monitoring)
11. [Contribution Guidelines](#11-contribution-guidelines)
12. [Development Roadmap](#12-development-roadmap)
13. [Security Considerations](#13-security-considerations)
14. [Open Questions & Future Work](#14-open-questions--future-work)

---

## 1. Project Overview

**GeoGuard Ledger** is an open-source research integrity system purpose-built for **Green Analytics Labs**. It provides a verifiable chain of custody for geochemical datasets by:

1. **Hashing** raw geochemical data (CSV, JSON, and XML uploads) to produce a tamper-evident fingerprint.
2. **Running AI-based anomaly detection** on the data to flag potential fabrication, instrumentation drift, or sampling errors.
3. **Anchoring integrity proofs** (the hash + anomaly report metadata) immutably onto the **Stellar blockchain** via **Soroban** smart contracts.

The system enables any third party to independently verify that a dataset has not been altered since its original submission, and that it passed (or failed) automated quality checks — without trusting a centralized authority.

### Key Design Principles

- **Verifiable by Default:** Every data submission produces an on-chain proof. Trust, but verify.
- **Privacy-Preserving:** Only hashes and metadata live on-chain. Raw data stays off-chain (IPFS or local storage in Phase 1).
- **Modular & Hackable:** Researchers should be able to swap out the AI model, hash algorithm, or blockchain without rewriting the entire system.
- **Open-Source First:** Apache 2.0 license. Community contributions are explicitly encouraged.

---

## 2. System Architecture

### 2.1 High-Level Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           USER / RESEARCHER                               │
│                                                                          │
│  ┌─────────────────────────────┐          ┌────────────────────────────┐ │
│  │   React Frontend (TS)       │          │  Freighter Browser Wallet  │ │
│  │   ┌───────────────────────┐ │          │  (Stellar Account Mgmt)    │ │
│  │   │ CSV Upload Widget     │ │          └────────────┬───────────────┘ │
│  │   │ Hash / AI Result View │ │                       │                 │
│  │   │ On-Chain Proof        │ │                       │                 │
│  │   │ Explorer / Dashboard  │ │                       │                 │
│  │   └──────────┬────────────┘ │                       │                 │
│  └──────────────┼──────────────┘                       │                 │
│                 │                                      │                 │
│                 │  REST / JSON                         │ Sign & Submit   │
│                 │  (Bearer Auth)                       │ (Soroban Tx)    │
│                 ▼                                      │                 │
│  ┌──────────────────────────────┐                      │                 │
│  │     Python Backend (FastAPI) │                      │                 │
│  │  ┌─────────────────────────┐ │                      │                 │
│  │  │ POST /api/v1/datasets   │◄├──────────────────────┘                 │
│  │  │  - CSV Parsing          │ │                                        │
│  │  │  - SHA-256 Hashing      │ │                                        │
│  │  │  - AI Anomaly Detection │ │                                        │
│  │  │  - Build Soroban Tx     │ │                                        │
│  │  │  - Store Metadata (DB)  │ │                                        │
│  │  └────────────┬────────────┘ │                                        │
│  │               │              │                                        │
│  │  ┌────────────▼────────────┐ │                                        │
│  │  │  GET /api/v1/datasets   │ │                                        │
│  │  │  POST /api/v1/verify    │ │                                        │
│  │  └────────────┬────────────┘ │                                        │
│  └───────────────┼──────────────┘                                        │
│                  │                                                       │
│         ┌────────┴────────┐                                              │
│         ▼                 ▼                                              │
│  ┌─────────────┐  ┌──────────────────┐                                   │
│  │ PostgreSQL  │  │ Soroban RPC      │                                   │
│  │ (Metadata,  │  │ (Stellar         │                                   │
│  │  Job State) │  │  Testnet/Mainnet) │                                   │
│  └─────────────┘  └────────┬─────────┘                                   │
│                            │                                             │
│                    ┌───────▼───────┐                                     │
│                    │ Soroban Smart │                                     │
│                    │   Contract    │                                     │
│                    │  (Rust/WASM)  │                                     │
│                    │               │                                     │
│                    │ anchor_hash() │                                     │
│                    │ verify()      │                                     │
│                    │ get_record()  │                                     │
│                    └───────────────┘                                     │
└──────────────────────────────────────────────────────────────────────────┘

  ┌──────────────────┐       ┌──────────────────────┐
  │   IPFS / Arweave  │       │  AI Model Service    │
  │  (Optional: Raw   │       │  (Isolation Forest   │
  │   Data Storage)   │       │   or LSTM-based)     │
  └──────────────────┘       └──────────────────────┘
```

### 2.2 Component Responsibilities

| Component | Responsibility |
|-----------|---------------|
| **React Frontend** | CSV upload UI, Freighter wallet connection, submission flow, proof verification, dataset dashboard. |
| **FastAPI Backend** | CSV parsing & validation, SHA-256 hashing, AI anomaly detection invocation, Soroban transaction construction, metadata persistence. |
| **PostgreSQL** | Stores dataset metadata, anomaly reports, transaction IDs, submission timestamps, researcher identities. |
| **Soroban Smart Contract** | Immutable on-chain storage of `(dataset_hash, anomaly_score, timestamp, submitter_pk)`. Provides `verify()` for independent proof checking. |
| **Freighter Wallet** | Stellar key management. Signs Soroban transactions before submission. |
| **IPFS (Phase 3)** | Decentralized raw data storage so third parties can re-hash and compare against the on-chain fingerprint. |
| **Event Indexer (Phase 3+)** | Persists on-chain `Anchored` events off-chain, enabling full history reconstruction independent of RPC event retention windows. |

---

## 3. Data Flow

### 3.1 Submission Flow (End-to-End)

```
Step 1: UPLOAD
    Researcher drags/drops a data file (CSV, JSON, or XML) into the React frontend.
    Frontend reads the file client-side and shows a preview (first 10 rows).

Step 2: PREVIEW & CONFIRM
    Researcher reviews the data preview, selects columns for hashing
    (default: all numeric columns), and clicks "Submit for Anchoring."

Step 3: ANALYZE (FastAPI) — no wallet required
    a. CSV is transmitted to POST /api/v1/datasets as multipart/form-data.
    b. Backend validates CSV structure (rows > 0, required columns present).
    c. Backend computes SHA-256 hash over the canonicalized CSV content.
       Canonicalization v1 (critical for deterministic hashing). The rule set is
       versioned as CANONICALIZATION_VERSION and advertised in API responses,
       because any change to it re-hashes every dataset:
       - RFC 4180-compliant CSV parsing with UTF-8 encoding (no BOM).
       - Line endings normalized to \n.
       - Every cell normalized to Unicode NFC.
       - Leading and trailing whitespace stripped from every cell.
       - Numeric cells — integers, decimals, and scientific notation alike —
         rendered as one canonical decimal form, rounded half-even to 6 decimal
         places (7.1234567 -> 7.123457, 1e-3 -> 0.001000, 5 -> 5.000000). A
         cell with leading zeros (e.g. 0001) is an identifier, not a number,
         and is left verbatim.
       - Row order preserved exactly as it appears in the file; rows are never
         sorted or reordered.
       - Exactly these rules are published, together with test vectors, so
         third parties can reproduce hashes (see docs/canonicalization.md).
    d. Backend invokes AI anomaly detection model:
       - Input: numeric columns from the CSV.
       - Output: anomaly_score (0.0–1.0), anomaly_flags (list of row indices),
         model_version.
    e. Backend stores the dataset as `analyzed` — no submitter, no transaction —
       and returns the dataset UUID, hash, and anomaly report.

    Nothing has been committed to the network at this point, so no wallet is
    involved: the hash and the anomaly report are readable before deciding
    whether to anchor at all.

Step 4: ANCHOR (wallet required)
    a. Frontend sends the researcher's address to POST /api/v1/datasets/:id/anchor.
    b. Backend binds that address as the dataset's submitter and builds the
       Soroban transaction:
       - Invokes contract function: anchor_hash(hash, anomaly_score, model_version).
       - Sets fee, source account, network passphrase.
    c. Backend marks the dataset `pending` and returns the unsigned XDR.

Step 5: WALLET SIGNING (Freighter)
    a. Frontend passes the transaction XDR to Freighter wallet.
    b. Researcher reviews and approves the transaction in Freighter.
    c. Freighter returns the signed transaction XDR.

Step 6: SUBMIT & CONFIRM
    a. Frontend sends the signed XDR to POST /api/v1/datasets/:id/submit.
    b. Backend submits the signed transaction to the Soroban RPC endpoint.
    c. Backend polls for transaction status until SUCCESS or FAILED.
    d. On SUCCESS: Backend stores the Stellar transaction hash, ledger number,
       and updates dataset status to "anchored."
    e. Backend returns the confirmation with on-chain proof details.

Step 7: VERIFICATION DISPLAY
    Frontend shows:
      - On-chain transaction link (Stellar Expert explorer).
      - Dataset hash, anomaly score, timestamp.
      - "Verified ✓" badge confirming on-chain anchoring.
```

### 3.2 Verification Flow (Third-Party Audit)

```
Step 1: REQUEST
    Auditor provides a dataset UUID or uploads a CSV claimed to be the original.

Step 2: BACKEND RE-VERIFICATION
    a. If CSV provided: backend re-computes SHA-256 hash.
    b. Backend queries the Soroban contract: verify(hash).
    c. Contract returns the stored record if it exists, or null.

Step 3: RESULT
    Backend returns:
     - match: true/false
     - on_chain_record: { hash, anomaly_score, timestamp, submitter }
     - re_computed_hash: (if CSV provided)
```

---

## 4. Smart Contract Logic (Soroban)

### 4.1 Contract: `GeoGuardLedger`

Written in **Rust** targeting the **Soroban SDK**. Compiled to WASM and deployed to a Stellar account on Testnet (eventually Mainnet).

### 4.2 Data Structures

```rust
/// Core record stored on-chain per dataset submission.
#[contracttype]
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct AnchorRecord {
    dataset_hash: BytesN<32>,   // SHA-256 hash of the canonicalized CSV
    anomaly_score: u32,         // Fixed-point: 0–10000 (representing 0.00–100.00%)
    model_version: Symbol,      // e.g., "isoforest_v1"
    timestamp: u64,             // Unix epoch seconds
    submitter: Address,         // Stellar public key of the submitting researcher
}

/// Record stored on-chain for a Merkle root committing to a batch of datasets.
#[contracttype]
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RootRecord {
    merkle_root: BytesN<32>,    // SHA-256 Merkle root over the batch leaves
    leaf_count: u32,            // Number of dataset leaves committed to
    submitter: Address,         // Stellar public key of the submitting researcher
    timestamp: u64,             // Unix epoch seconds
}
```

### 4.3 Contract Storage Layout

Soroban provides three storage types with distinct durability and cost profiles:

| Storage Type | Durability | Use Case |
|---|---|---|
| **Persistent** | Archived on TTL expiry (recoverable); small per-entry rent. | Long-lived anchor records. |
| **Instance** | Expires with the contract instance; loaded into memory on every invocation. | Small, frequently accessed global state. |
| **Temporary** | Permanently deleted on TTL expiry. | Ephemeral data (nonces). Never use for anchors. |

**Storage Layout:**

| Key | Value | Storage Type | Purpose |
|-----|-------|:---:|---------|
| `Admin` | `Address` | Instance | Contract administrator (can upgrade, pause). |
| `Record(dataset_hash)` | `AnchorRecord` | **Persistent** | Per-dataset anchoring record. Archived on expiry but recoverable. |
| `SubmitCount(submitter)` | `u32` | Persistent | How many datasets a researcher has anchored. |
| `TotalAnchored` | `u32` | Instance | Global counter of all anchored datasets. |
| `Root(merkle_root)` | `RootRecord` | **Persistent** | Per-batch Merkle root record. One entry covers every dataset in the batch. |
| `BatchCount(submitter)` | `u32` | Persistent | How many batches a researcher has anchored. |
| `TotalBatches` | `u32` | Instance | Global counter of all anchored Merkle roots. |

**Critical Design Choice:** `Record` entries use **Persistent** storage so that even if rent lapses and the ledger entry is archived, the proof is not permanently deleted — it can be restored. Temporary storage is explicitly avoided for integrity proofs because expired Temporary entries are irretrievably destroyed.

### 4.4 Functions

#### `initialize(admin: Address)`
- **Access:** Invoked once during deployment.
- **Effect:** Sets the `Admin` address. Sets `TotalAnchored` to 0.

#### `anchor_hash(submitter: Address, dataset_hash: BytesN<32>, anomaly_score: u32, model_version: Symbol) -> AnchorRecord`
- **Access:** Public (submitters pay gas).
- **Preconditions:**
  - `dataset_hash` must not already exist (no overwrites).
  - `submitter` must be authenticated (requires `require_auth` for the submitter address).
- **Effect:**
  - Stores a new `AnchorRecord` keyed by `dataset_hash`.
  - Extends the new entry's TTL to the full record budget (~180 days). A record is written once and never modified, so without this it would carry only the network's *minimum* persistent-entry TTL and be archived within days, making `verify_integrity` stop answering for a dataset nobody had tampered with.
  - Increments `SubmitCount(submitter)`.
  - Increments `TotalAnchored`.
  - Emits an `Anchored` event.
- **Returns:** The newly created `AnchorRecord`.

#### `verify_integrity(dataset_hash: BytesN<32>) -> Option<AnchorRecord>`
- **Access:** Public read-only (no auth required, no gas — uses Soroban's `read_only`).
- **Effect:** None (pure query).
- **Returns:** The `AnchorRecord` if the hash exists on-chain, otherwise `None`.

#### `get_record_count(submitter: Address) -> u32`
- **Access:** Public read-only.
- **Returns:** Number of datasets anchored by a given researcher.

#### `get_total_anchored() -> u32`
- **Access:** Public read-only.
- **Returns:** Global count of all anchored datasets.

#### `extend_ttl(dataset_hash: BytesN<32>, extend_to: u32)`
- **Access:** Public (permissionless — anyone can pay to keep records alive).
- **Effect:** Extends the Time-To-Live (TTL) of the `Record(dataset_hash)` Persistent ledger entry to `extend_to` (expressed as a ledger sequence number). The entry is renewed only once its remaining TTL drops below `extend_to - TTL_RENEWAL_MARGIN`, so a call reliably keeps a record far from expiry instead of no-opping on one that already sits near the target.
- **Rationale:** Stellar's state rent model requires periodic TTL renewal, and a record's write-time bump is only a ~180-day reprieve. This function allows the backend (or any third party) to proactively extend the lifespan of anchored records, keeping queries fast and free of archival-restoration overhead.
- **Caller:** `backend/app/jobs/renew_ttl.py`, signed by the operational "rent payer" account.

#### `anchor_root(submitter: Address, merkle_root: BytesN<32>, leaf_count: u32) -> RootRecord`
- **Access:** Public (submitters pay gas).
- **Preconditions:**
  - `leaf_count` must be greater than 0.
  - `merkle_root` must not already exist (no overwrites).
  - `submitter` must be authenticated (requires `require_auth` for the submitter address).
- **Effect:**
  - Stores a new `RootRecord` keyed by `merkle_root`.
  - Extends the new entry's TTL to the full root budget (~180 days), so a batch only ever needs one renewal.
  - Increments `BatchCount(submitter)`.
  - Increments `TotalBatches`.
  - Emits a `RootAnchored` event.
- **Returns:** The newly created `RootRecord`.
- **Rationale:** One root costs one Persistent entry (and one rent obligation) no matter how many datasets it commits to. This is what decouples anchoring cost from submission volume.

#### `get_root(merkle_root: BytesN<32>) -> Option<RootRecord>`
- **Access:** Public read-only.
- **Returns:** The `RootRecord` if the root is anchored, otherwise `None`.

#### `verify_inclusion(merkle_root: BytesN<32>, dataset_hash: BytesN<32>, index: u32, siblings: Vec<BytesN<32>>) -> bool`
- **Access:** Public read-only (no gas).
- **Effect:** Recomputes the root from the dataset hash and the bottom-up `siblings` path, starting at leaf position `index` and halving it once per level, then compares against the anchored `merkle_root`.
- **Returns:** `true` only when the root is anchored **and** the proof reconstructs it; `false` when the root is unknown or the proof does not match.
- **Merkle scheme (normative):**
  - Leaf: `SHA256(0x00 || dataset_hash)`
  - Internal node: `SHA256(0x01 || left || right)`
  - A level with an odd number of nodes pairs its final node with itself.
  - The `0x00`/`0x01` prefixes domain-separate leaves from interior nodes.
  - The off-chain implementation in `backend/app/services/merkle.py` reproduces these rules byte for byte.

#### `get_batch_count(submitter: Address) -> u32`
- **Access:** Public read-only.
- **Returns:** Number of Merkle roots anchored by a given researcher.

#### `get_total_batches() -> u32`
- **Access:** Public read-only.
- **Returns:** Global count of all anchored Merkle roots.

#### `extend_root_ttl(merkle_root: BytesN<32>, extend_to: u32)`
- **Access:** Public (permissionless).
- **Effect:** Extends the TTL of the `Root(merkle_root)` Persistent entry to `extend_to`.
- **Rationale:** Batch roots are the long-lived entries that need renewal, so renewing one root keeps every dataset in the batch queryable.

#### `transfer_admin(new_admin: Address)`
- **Access:** Admin only (`require_auth` for current admin).
- **Effect:** Updates the `Admin` address.

### 4.5 Events

```rust
/// Emitted when a new dataset is anchored.
event Anchored {
    dataset_hash: BytesN<32>,
    submitter: Address,
    timestamp: u64,
}

/// Emitted when a batch Merkle root is anchored.
event RootAnchored {
    merkle_root: BytesN<32>,
    submitter: Address,
    leaf_count: u32,
    timestamp: u64,
}
```

**Event Retention Note:** Standard Stellar RPC nodes only retain event history for a limited window (typically ~2 weeks). For long-term auditability, the backend must persist `Anchored` events into PostgreSQL as they are emitted. This ensures the system can reconstruct its full history even if all on-chain events have been pruned. For decentralized recovery, a Stellar data indexer (e.g., a custom Horizon listener) may be employed to mirror event history off-chain.

### 4.6 Error Handling

The contract defines five error variants for predictable error handling by clients (backend and frontend). Each maps to a numeric contract error code returned in the failed transaction result, so clients can branch on it programmatically:

| Code | Variant | Description |
|:---:|---|-----------|
| 1 | `NotInitialized` | Contract has not been initialized (no `Admin` set). |
| 2 | `AlreadyInitialized` | `initialize()` called more than once. |
| 3 | `HashAlreadyAnchored` | Attempted to anchor a dataset hash that already exists on-chain. |
| 4 | `HashNotFound` | Attempted `extend_ttl()` on a non-existent hash. |
| 5 | `Unauthorized` | Caller lacks the required authorization (e.g., non-admin for `transfer_admin`). |

```rust
/// Defined in contracts/geoguard-ledger/src/errors.rs
#[derive(Copy, Clone, Debug, PartialEq, Eq)]
#[contracterror]
pub enum Error {
    NotInitialized = 1,
    AlreadyInitialized = 2,
    HashAlreadyAnchored = 3,
    HashNotFound = 4,
    Unauthorized = 5,
}
```

Frontend and backend clients should parse these error codes from the Soroban transaction result to provide meaningful user feedback (e.g., "This dataset has already been anchored" versus "Network error — please try again").

The batching entry points extend this with two additional call traps, matching the existing `anchor_hash` style of failing loudly rather than silently overwriting state: `anchor_root` rejects an empty batch (`Batch must contain at least one leaf`) and a root that is already anchored (`Merkle root already anchored`), and `extend_root_ttl` rejects an unknown root (`Merkle root not found`).

### 4.7 Gas & Cost Model

- Each `anchor_hash` call stores ~100 bytes of data (32 + 4 + ~12 + 8 + 32).
- **State Rent & TTL:** Stellar Soroban charges ongoing rent for ledger entries. Each Persistent entry has a Time-To-Live (TTL) measured in ledgers (~5 seconds per ledger). When TTL expires, the entry is archived (recoverable for Persistent, permanently deleted for Temporary). Someone must periodically call `extend_ttl()` to keep records alive and queryable without archival-restoration overhead.
  - **Important:** TTL expiry is **not** a security mechanism — anyone can permissionlessly renew any entry. Validity logic (timestamps) lives inside the contract code, not in the TTL.
- Estimated cost per anchoring (Testnet, subject to change): ~0.5–1 XLM, plus ongoing rent of ~0.01–0.05 XLM/year per record.
- **Batch anchoring (`anchor_root`):** Anchors a Merkle root instead of individual hashes, collapsing O(n) rent costs into O(1) by committing thousands of datasets under a single Persistent key. Individual datasets are verified with a Merkle inclusion proof (`verify_inclusion`), which the backend generates off-chain in `app/services/merkle.py` and stores alongside each dataset. This is the primary lever for scaling: anchoring cost and rent obligations no longer grow with the number of submissions, and a whole batch is kept alive by renewing one root.

---

## 5. Backend API Specification (FastAPI)

### 5.1 Base URL

```
Development: http://localhost:8000/api/v1
```

### 5.2 Endpoints

Each endpoint notes whether it requires the `X-API-Key` header and whether it is
rate limited. `Auth: API key required` means the header must match a key in
`API_KEYS` (unless `API_KEYS` is empty, which disables authentication in
development). `Rate limit` marks the endpoints counted per client IP over a
sliding window. The full model is in
[§5.3 Authentication & Authorization](#53-authentication--authorization).

#### `POST /api/v1/datasets`
Analyze a new geochemical dataset: canonicalize, hash, and score it. No wallet
is required, and no transaction is returned — anchoring is a separate step.

**Auth:** API key required. **Rate limit:** applies — this is the upload/analyze
endpoint, so it is the most expensive call in the API (`429` with `Retry-After`
when exceeded).

**Request:**
```
Content-Type: multipart/form-data
  - file: CSV, JSON, or XML file (required)
```

Anchoring is performed by `POST /api/v1/datasets/:id/anchor`.

**Status:** the dataset is stored as `analyzed` (`analyzed | pending |
anchored | failed`), with `submitter_address` NULL until it is anchored.

**Supported formats:** `.csv`, `.json`, and `.xml` (detected from the filename
extension, case-insensitive). CSV and JSON are normalized to a single canonical
CSV representation, so the same data uploaded in either format produces the same
`dataset_hash`. XML is canonicalized **as XML** — comments and processing
instructions are dropped, attributes sorted alphabetically, insignificant
whitespace removed, and no BOM is emitted — and hashed as XML, so formatting
differences never change the digest. The canonical XML is then flattened into
rows for anomaly detection. Malformed XML, and XML with fewer than two numeric
feature columns, are rejected with `400 Bad Request`.

**Limits:** the request body is capped at `MAX_UPLOAD_SIZE_BYTES` (default
50 MB) and enforced server-side before the body is read. Oversized uploads are
rejected with `413 Payload Too Large`.

`anomaly_report.warnings` carries domain-informed plausibility findings
(impossible or implausible geochemical values). Unlike `score`/`flags`, these
come from deterministic range checks rather than the statistical model, so they
are also reported for datasets too small to score. See
[docs/ai_model.md](docs/ai_model.md#geochemical-range-validation).

**Response (201 Created):**
```json
{
  "dataset_id": "uuid",
  "dataset_hash": "abc123...",
  "anomaly_report": {
    "score": 0.12,
    "flags": [42, 87],
    "model_version": "isoforest_v1",
    "summary": "12% anomaly probability. 2 rows flagged.",
    "warnings": ["[ERROR] pH: 1 value(s) outside the plausible range 0 to 14 (rows 4)"]
  },
  "created_at": "2026-07-05T12:00:00Z"
}
```

#### `POST /api/v1/datasets/{dataset_id}/anchor`
Bind the researcher's Stellar address to an analyzed dataset and build the
unsigned anchoring transaction. This is the instance of the flow that needs a
wallet, because it produces the transaction that must be signed.

**Auth:** API key required. **Rate limit:** not applied.

**Request:**
```json
{
  "submitter_address": "GABC..."
}
```

**Behaviour:**
- The address must be a Stellar public key (starts with `G`), and becomes both
  the transaction's source account and the dataset's recorded submitter.
- A dataset already bound to a different address is refused with `403`; one
  already `anchored` with `409`. An `analyzed` or `pending` dataset can be
  anchored again, which is what retrying a rejected signature looks like.
- The address is never validated as a signature, so what it proves is *which
  account paid to anchor the hash*, not who the researcher is.

**Response (200 OK):**
```json
{
  "dataset_id": "uuid",
  "dataset_hash": "abc123...",
  "unsigned_transaction_xdr": "AAAAAgAAA..."
}
```

#### `POST /api/v1/datasets/{dataset_id}/submit`
Submit a researcher-signed transaction to the Stellar network.

**Auth:** API key required. **Rate limit:** not applied.

**Request:**
```json
{
  "signed_transaction_xdr": "AAAAAgAAA..."
}
```

**Response (200 OK):**
```json
{
  "dataset_id": "uuid",
  "status": "anchored",
  "stellar_tx_hash": "def456...",
  "ledger_number": 1234567,
  "explorer_url": "https://stellar.expert/explorer/testnet/tx/def456...",
  "anchored_at": "2026-07-05T12:01:30Z"
}
```

#### `GET /api/v1/datasets`
List all datasets for a researcher.

**Auth:** public. **Rate limit:** not applied.

**Response (200 OK):**
```json
{
  "datasets": [
    {
      "dataset_id": "uuid",
      "dataset_hash": "abc123...",
      "status": "anchored",
      "anomaly_score": 0.12,
      "created_at": "2026-07-05T12:00:00Z"
    }
  ],
  "total": 42
}
```

#### `GET /api/v1/datasets/{dataset_id}`
Get full details for a single dataset.

**Auth:** public. **Rate limit:** not applied.

#### `POST /api/v1/verify`
Verify a dataset against its on-chain proof.

**Auth:** public — permissionless verification is the point. **Rate limit:**
applies; the file mode re-hashes an upload and every mode queries the Soroban
RPC, so calls are counted per client IP (`429` with `Retry-After` when
exceeded).

**Request:**
```json
{
  "dataset_id": "uuid"         // Option A: look up by ID
  // OR
  "dataset_hash": "abc123...", // Option B: verify by hash directly
  "file": "..."                // Option C: re-upload CSV, JSON, or XML to re-hash and verify
}
```

**Response (200 OK):**
```json
{
  "match": true,
  "on_chain_record": {
    "dataset_hash": "abc123...",
    "anomaly_score": 0.12,
    "model_version": "isoforest_v1",
    "timestamp": 1751715300,
    "submitter": "GABC..."
  },
  "local_record": {
    "dataset_id": "uuid",
    "anomaly_score": 0.12
  },
  "inclusion": {
    "root": "64-char-hex",
    "leaf_index": 0,
    "proof": ["64-char-hex", "..."],
    "batch_id": "uuid",
    "verified_locally": true,
    "verified_on_chain": true
  }
}
```

`inclusion` is `null` for datasets anchored individually. For batched datasets it
carries everything a third party needs to verify membership against the anchored
Merkle root: the root, the leaf position, and the bottom-up sibling path.
`verified_locally` re-runs the proof check in the backend, while
`verified_on_chain` reports the contract's own `verify_inclusion` verdict (or
`null` when the check could not be evaluated).

#### `POST /api/v1/batches`
Build a Merkle root over a set of datasets and return an unsigned root-anchoring transaction.

**Auth:** API key required. **Rate limit:** not applied.

**Request:**
```json
{
  "submitter_address": "GABC...",
  "dataset_ids": ["uuid-1", "uuid-2"]   // leaf order follows this list
}
```

**Behaviour:**
- All datasets must exist, not already be in a batch, and either have no submitter yet (they were only analyzed) or already belong to `submitter_address`. A member with no submitter is claimed by this call, since building the root transaction is the first point at which the address is needed.
- The batch may not exceed `MAX_BATCH_SIZE` (default 1024) datasets, and `dataset_ids` must be unique.
- Leaves are committed in the order given, and each dataset records its `leaf_index`, `merkle_root`, and `merkle_proof`.

**Response (201 Created):**
```json
{
  "batch_id": "uuid",
  "merkle_root": "64-char-hex",
  "leaf_count": 2,
  "unsigned_transaction_xdr": "AAAA...",
  "leaves": [
    {
      "dataset_id": "uuid-1",
      "dataset_hash": "64-char-hex",
      "leaf_index": 0,
      "merkle_proof": ["64-char-hex"],
      "anomaly_score": 0.12
    }
  ],
  "created_at": "2026-09-12T09:46:41Z"
}
```

#### `POST /api/v1/batches/{batch_id}/submit`
Submit the researcher-signed root transaction. On success the batch and every dataset it covers are marked `anchored` and share the one transaction hash.

**Auth:** API key required. **Rate limit:** not applied.

#### `GET /api/v1/batches`
List batches, most recent first.

**Auth:** public. **Rate limit:** not applied.

#### `GET /api/v1/batches/{batch_id}`
Fetch a single batch by ID.

**Auth:** public. **Rate limit:** not applied.

#### `GET /api/v1/health`
Health check endpoint. Probes the Soroban RPC endpoint on every call and
reports the real result: `{"status": "ok", "soroban_rpc": "connected"}` when
the RPC is reachable and healthy, `{"status": "ok", "soroban_rpc":
"unreachable"}` otherwise. `status` describes the API itself, so it stays
`"ok"` while a dependency is down. The probe timeout is configurable via
`SOROBAN_RPC_HEALTH_TIMEOUT_SECONDS`.

**Auth:** public — a probe that needs credentials is not a useful probe.
**Rate limit:** not applied.

#### `GET /api/v1/maintenance/ttl-status`
Reports how much life the anchored entries have left, nested under `roots` and
`records`. Anchors are Persistent ledger entries, so if renewal stops working
they are eventually archived and verification silently stops answering — this
endpoint is how that shows up as a metric instead. Each block carries the
anchored count, how many are due for renewal, how many are already past their
recorded expiry, how many are failing to renew, and the next deadline and last
renewal. `records` covers standalone anchors only; a batched dataset is covered
by its batch root, so it is counted there instead. Kept out of `/health` so
liveness probes do not pay for a database aggregate.

**Auth:** public. **Rate limit:** not applied.

### 5.3 Authentication & Authorization

**Current:** Write endpoints require an `X-API-Key` header whose value matches one of
the keys configured in the comma-separated `API_KEYS` environment variable.
Gated endpoints are those that upload or anchor: `POST /datasets`,
`POST /datasets/{id}/anchor`, `POST /datasets/{id}/submit`, `POST /batches`, and
`POST /batches/{id}/submit`. Comparison is constant-time, and every configured
key is compared even after a match, so response timing reveals neither a wrong
key nor which key (or position) succeeded; multiple keys may be listed at once so
one can be rotated without downtime. **When `API_KEYS` is empty, authentication
is disabled** — the development default, so a local checkout runs with no setup,
while deployments are expected to set at least one key.

**Stays public:** read endpoints (`GET /datasets`, `GET /datasets/{id}`,
`GET /batches`, `GET /batches/{id}`), `POST /verify`, and `GET /health`.
Permissionless verification is a feature — any third party must be able to check
a proof without a shared secret — and a health probe that needs credentials is
not a useful probe. `researcher_id` for an anchor is still derived from the
submitter's Stellar public key embedded in the signed transaction XDR, so the
API key gates *access* while the wallet signature proves *who anchored*.

**Abuse limits:** the upload and verification endpoints parse and hash a file
(verification also queries the Soroban RPC), so they are additionally rate
limited per client IP over a sliding window. `RATE_LIMIT_REQUESTS` (default 30)
and `RATE_LIMIT_WINDOW_SECONDS` (default 60) bound each endpoint separately, and
exceeding one returns `429 Too Many Requests` with a `Retry-After` header. The
counters are in-process, which bounds a single abusive client; a shared store
(for example Redis) is the natural replacement if the API runs several replicas.

**Phase 3+ (Planned):** validate keys against a table of registered researchers
rather than a static list, so keys can be issued, scoped, and revoked per
researcher instead of by redeploying.

**Design Principle:** The backend never holds or requests Stellar secret keys. All transaction signing happens client-side via Freighter wallet. The backend only handles unsigned XDR construction and signed XDR submission — the private key never leaves the browser extension.

### 5.4 Background Tasks

- **Transaction Status Polling:** After the backend submits a signed transaction, a background `asyncio` task polls the Soroban RPC every 2 seconds (up to 30 seconds) for the transaction result.
- **AI Model Inference:** The anomaly detection model runs synchronously during the POST request in Phase 1. In Phase 3, this may move to a Celery/Redis task queue for long-running models.
- **TTL Renewal Scheduler (Phase 3+):** A periodic background task (e.g., Celery Beat or a simple `asyncio` loop) queries on-chain anchor records approaching their TTL expiry and automatically submits `extend_ttl()` transactions. This acts as an automated "rent payer" so researchers don't need to worry about their proofs being archived. Green Analytics Labs may subsidize these renewal costs.

---

## 6. Frontend Specification (React + TypeScript)

### 6.1 Tech Stack

| Layer | Choice |
|-------|--------|
| Framework | React 18+ (TypeScript) |
| Build Tool | Vite |
| Styling | Tailwind CSS |
| Stellar SDK | `@stellar/stellar-sdk` + `@stellar/freighter-api` |
| HTTP Client | `axios` or native `fetch` |
| Routing | React Router v6 |
| State Management | React Context + `useReducer` (or Zustand if complexity grows) |

### 6.2 Pages / Views

| Route | Component | Purpose |
|-------|-----------|---------|
| `/` | `DashboardPage` | Overview: total datasets anchored, recent submissions, quick actions. |
| `/upload` | `UploadPage` | CSV drag-and-drop upload, column selection, preview, submit. |
| `/datasets` | `DatasetListPage` | Table of all submitted datasets with status and batch badges. |
| `/datasets/:id` | `DatasetDetailPage` | Full detail: hash, anomaly report, on-chain tx link, batch membership with inclusion proof, verify button. |
| `/verify` | `VerifyPage` | Upload or paste a hash to verify against the blockchain. |
| `/settings` | `SettingsPage` | Stellar network selection (Testnet/Mainnet), wallet connection. |

### 6.3 Key UI Components

| Component | Description |
|-----------|-------------|
| `CsvDropzone` | Drag-and-drop area with file validation (.csv, .json, .xml), row count display, preview table. |
| `WalletConnector` | "Connect Freighter" button. Shows connected address, network, and XLM balance. |
| `SubmissionWorkflow` | Stepper: Upload → Preview → AI Report → Sign → Confirmed. |
| `AnomalyBadge` | Color-coded badge (green < 5%, yellow 5–20%, red > 20%). |
| `TxExplorerLink` | Clickable link to Stellar Expert for a given transaction hash. |
| `VerificationResult` | Side-by-side comparison of on-chain record vs. local/computed values. |
| `DatasetTable` | Table with columns: date, dataset, hash (truncated), batch, anomaly score, status, transaction. |
| `SingleAnchorFlow` | Full single-dataset anchor flow: upload → preview → AI report → sign → confirmed. |
| `BatchAnchorFlow` | Collect datasets, commit them to one Merkle root, and anchor the whole batch with one signature. |
| `MerkleProof` | Batch root, leaf position, sibling path, and local/on-chain verdicts for an inclusion proof. Its verdict can be suppressed where the proof is shown as a claim that has not been checked yet. |
| `BatchBadge` | Compact marker showing which leaf of a batch a dataset occupies; used in the dataset table and the detail header. |

### 6.4 Freighter Integration Flow

```
1. User clicks "Connect Freighter" → Freighter popup → User approves.
2. Frontend stores the public key (G... address) in React state.
3. During submission:
   a. Backend returns unsigned transaction XDR.
   b. Frontend calls freighterApi.signTransaction(xdr, { networkPassphrase }).
   c. Freighter prompts user to review and sign.
   d. Signed XDR is sent to backend for submission.
```

### 6.5 UX States to Handle

- **Wallet not installed:** Show "Install Freighter" link with instructions.
- **Wrong network:** Show a warning if wallet is on Mainnet but app expects Testnet (and vice versa).
- **Transaction pending:** Show a spinner with "Waiting for confirmation… (Ledger X)".
- **Transaction failed:** Show error message with the failure reason from the RPC.
- **CSV too large:** Enforce a configurable max file size (default: 50 MB). Show a clear error.

---

## 7. Repository Structure

```
geoguard-ledger/
├── README.md                   # Project overview, quickstart, badges
├── SPECIFICATION.md            # This file
├── LICENSE                     # Apache 2.0
├── CONTRIBUTING.md             # Contribution guide (see §11)
├── CODE_OF_CONDUCT.md          # Contributor Covenant
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md
│   │   └── feature_request.md
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── workflows/
│       ├── ci.yml              # Lint, test, build
│       └── contract-test.yml   # Soroban contract tests
│
├── contracts/                  # Soroban Smart Contracts
│   ├── geoguard-ledger/
│   │   ├── Cargo.toml
│   │   ├── src/
│   │   │   ├── lib.rs          # Contract entry point
│   │   │   ├── storage.rs      # Persistent storage logic
│   │   │   ├── types.rs        # AnchorRecord, events
│   │   │   ├── errors.rs       # Contract-specific errors
│   │   │   └── test.rs         # Unit tests (cargo test)
│   │   └── Makefile            # build, test, deploy targets
│   └── README.md               # Contract docs: build, deploy, invoke
│
├── backend/                    # Python FastAPI Backend
│   ├── pyproject.toml          # Dependencies (managed with uv)
│   ├── alembic/                # Database migrations
│   │   └── versions/
│   ├── uv.lock                 # Locked dependency versions
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py             # FastAPI app, CORS, lifespan
│   │   ├── config.py           # Settings (env vars, Pydantic)
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── v1/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── datasets.py    # Dataset endpoints
│   │   │   │   ├── batches.py     # Merkle batch endpoints
│   │   │   │   ├── verify.py      # Verification endpoints
│   │   │   │   ├── maintenance.py # TTL renewal status
│   │   │   │   └── health.py      # Health check
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── dataset.py      # SQLAlchemy model
│   │   │   └── batch.py        # Merkle batch model (incl. TTL deadlines)
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── hasher.py       # SHA-256 hashing + canonicalization
│   │   │   ├── anomaly.py      # AI anomaly detection service
│   │   │   ├── merkle.py       # Merkle tree construction + inclusion proofs
│   │   │   ├── ttl_renewal.py  # Entry expiry math + renewal orchestration
│   │   │   └── soroban.py      # Soroban RPC client, tx building
│   │   ├── jobs/
│   │   │   ├── __init__.py
│   │   │   └── renew_ttl.py    # Scheduled TTL renewal job (roots + records)
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── session.py      # Async SQLAlchemy session
│   │   │   └── base.py         # Declarative base
│   │   └── core/
│   │       ├── __init__.py
│   │       ├── security.py     # Auth (API keys / JWT in later phases)
│   │       └── exceptions.py   # Custom exception handlers
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_datasets.py
│   │   ├── test_batches.py
│   │   ├── test_merkle.py
│   │   ├── test_ttl_renewal.py  # Expiry math, selection, renewal, job
│   │   ├── test_maintenance.py # TTL status endpoint + anchoring seams
│   │   ├── test_verify.py
│   │   └── fixtures/
│   │       └── sample.csv
│   ├── Dockerfile
│   └── .env.example
│
├── frontend/                   # React Frontend
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── index.html
│   ├── public/                 # Static assets (Phase 4)
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── App.test.tsx         # Component smoke tests (Vitest)
│   │   ├── routes.tsx          # React Router definitions
│   │   ├── api/
│   │   │   ├── client.ts       # Axios instance, interceptors
│   │   │   ├── datasets.ts     # Dataset API calls
│   │   │   ├── batches.ts      # Batch API calls
│   │   │   └── verify.ts       # Verification API calls
│   │   ├── components/
│   │   │   ├── CsvDropzone.tsx
│   │   │   ├── WalletConnector.tsx
│   │   │   ├── SubmissionStepper.tsx
│   │   │   ├── SingleAnchorFlow.tsx
│   │   │   ├── BatchAnchorFlow.tsx
│   │   │   ├── MerkleProof.tsx
│   │   │   ├── BatchBadge.tsx
│   │   │   ├── AnomalyBadge.tsx
│   │   │   ├── TxExplorerLink.tsx
│   │   │   ├── DatasetTable.tsx
│   │   │   └── VerificationResult.tsx
│   │   ├── pages/
│   │   │   ├── DashboardPage.tsx
│   │   │   ├── UploadPage.tsx
│   │   │   ├── DatasetListPage.tsx
│   │   │   ├── DatasetDetailPage.tsx
│   │   │   ├── VerifyPage.tsx
│   │   │   └── SettingsPage.tsx
│   │   ├── hooks/
│   │   │   ├── useWallet.ts    # Freighter connection hook
│   │   │   ├── useDatasets.ts  # Data fetching hook
│   │   │   └── useVerify.ts   # Verification hook
│   │   ├── context/
│   │   │   └── WalletContext.tsx
│   │   ├── types/
│   │   │   └── index.ts        # Shared TypeScript types
│   │   └── utils/
│   │       ├── csv.ts          # Client-side CSV parsing/preview
│   │       └── stellar.ts      # Stellar helpers (network config, etc.)
│   ├── tests/
│   │   ├── components/
│   │   │   └── index.test.tsx  # Component export smoke tests
│   │   └── pages/
│   │       └── index.test.tsx  # Page export smoke tests
│   ├── public/                 # favicon + apple-touch-icon + og-image
│   └── Dockerfile
│
├── docker-compose.yml          # Orchestrates backend + db + frontend
├── assets/                     # Brand assets: logo.svg + avatar PNGs
├── scripts/
│   ├── setup_dev.sh            # One-command dev environment setup
│   ├── deploy_contract.sh      # Deploy Soroban contract to Testnet
│   ├── seed_db.py              # Seed database with sample datasets
│   └── generate_logo.py        # Regenerate the logo SVG + PNGs
│
└── docs/
    ├── architecture.md         # Detailed architecture decisions
    ├── ai_model.md             # AI anomaly detection approach
    └── api_reference.md        # Full API reference (generated)
```

---

## 8. Testing Strategy

Testing is mandatory at every layer of the stack. All PRs must include tests for new functionality.

### 8.1 Smart Contract Testing (Rust)

**Framework:** `cargo test` with the Soroban SDK `testutils` feature.

**Key patterns:**
- Use `Env::default()` and `register_contract` for isolated test environments.
- Use `Address::generate(&env)` for deterministic but unique test addresses.
- Use `#[should_panic(expected = "...")]` to verify error conditions.
- Test all happy paths, error paths, and state transitions.

**Coverage targets:**
- 100% branch coverage on all contract functions.
- Every error variant must have at least one test that triggers it.
- Verify that `anchor_hash` prevents double-anchoring.
- Verify that `transfer_admin` rejects unauthorized callers.
- Verify that `extend_ttl` fails for non-existent hashes.
- Verify that `anchor_root` prevents empty and duplicate batches.
- Verify inclusion proofs for even, odd, and single-leaf trees, and that a proof is rejected for a leaf outside the batch or against an unanchored root.

**Run:** `cd contracts/geoguard-ledger && cargo test`

### 8.2 Backend Testing (Python)

**Framework:** `pytest` with `pytest-asyncio` for async endpoint tests.

**Test structure:**
```
backend/tests/
├── conftest.py          # Fixtures: test client, DB session, mocked Soroban RPC
├── test_datasets.py     # POST /datasets, submission, listing
├── test_batches.py      # POST /batches, root submission, membership checks
├── test_merkle.py       # Merkle roots and inclusion-proof golden vectors
├── test_verify.py       # POST /verify, hash comparison
├── test_parser.py       # CSV/JSON parsing and canonical conversion
├── test_parser_json_types.py # JSON type preservation / hash equivalence
├── test_xml.py          # XML canonicalization, hashing, and upload pipeline
├── test_validation.py   # Geochemical range checks + report integration
├── test_uploads.py      # Server-side size limits on both upload endpoints
├── test_health.py       # Real Soroban RPC connectivity reporting
├── e2e_full_api.py      # End-to-end API integration test
├── e2e_submission_flow.py # Full submission flow integration test
└── fixtures/
    ├── sample.csv       # Deterministic test CSV
    └── sample.xml       # Equivalent deterministic test XML
```

**Key patterns:**
- Use `httpx.AsyncClient` with the FastAPI `TestClient` for integration tests.
- Mock the Soroban RPC client (`soroban.py`) to avoid external network calls.
- Use an in-memory SQLite database (`aiosqlite`) for isolated test DB state.
- Test hash determinism: the same CSV must always produce the same SHA-256.
- Test format equivalence: the same data uploaded as CSV and as JSON must hash identically.
- Test XML canonicalization: attribute order, indentation, comments, processing instructions, and a UTF-8 BOM must not change the XML hash.
- Test canonicalization edge cases: BOM characters, `\r\n` line endings, trailing whitespace.
- Test server-side upload limits return `413`, independently of the frontend check.
- Test the health endpoint against mocked connected and unreachable RPC states.

**Coverage targets:**
- All API endpoints: success responses, validation errors, and edge cases.
- Hasher service: identical CSVs produce identical hashes; modified CSVs produce different hashes.
- Anomaly service: valid CSV returns a properly structured anomaly report.

**Run:** `cd backend && uv run pytest`

### 8.3 Frontend Testing (TypeScript)

**Framework:** Vitest + React Testing Library.

**Key patterns:**
- Component tests: render components and assert on user-visible output, not merely that a component is exported.
- Hook tests: exercise `useDatasets` and `useVerify` in isolation with mocked API modules.
- Routing tests: pin the `routes.tsx` table and render `App` at each path, with Freighter mocked.
- Utility tests: CSV/JSON/XML parsing (including RFC 4180 quoting), Stellar helper functions.

**Coverage targets:**
- All UI states: loading, success, error, empty.
- CsvDropzone: file validation (.csv, .json, .xml), size limits, preview rendering, drag-and-drop.
- WalletConnector: connected, disconnected, error states.
- AnomalyBadge: every score tier and size; AnomalyWarnings: error vs warning styling.
- DatasetTable, SubmissionStepper and ErrorBoundary: every render state, including recovery.
- MerkleProof: verdict tiers (on-chain, local-only, failed), proof paths, and the single-leaf empty path.
- BatchAnchorFlow: add/remove members, leaf order, root creation, single-signature anchoring, and failure paths.
- Batch membership: standalone vs. batched datasets, a single-leaf batch's empty path, and an as-yet-unrecorded path.
- DatasetTable and DatasetDetailPage: the batch column and badge, and the detail page's proof section, batch-transaction label and re-check link.
- VerificationResult: individually anchored, batch-included, and failed-proof outcomes.

**Run:** `cd frontend && npm test`

### 8.4 End-to-End Testing

**Phase 2+:** E2E tests using Playwright or Cypress that simulate the full user journey:
1. Connect Freighter wallet (mocked).
2. Upload a CSV file.
3. Review AI anomaly report.
4. Sign and submit the transaction.
5. Verify the dataset appears as "anchored" on the dashboard.

---

## 9. CI/CD Pipeline

### 9.1 Continuous Integration

GitHub Actions workflows enforce quality gates on every PR and push to `main`:

**`ci.yml`** — Full-stack validation:
| Job | Commands |
|-----|----------|
| **Contract Lint & Build** | `cargo fmt --check`, `cargo clippy -- -D warnings`, `cargo build --target wasm32-unknown-unknown --release` |
| **Contract Test** | `cargo test` (all unit tests) |
| **Backend Lint & Typecheck** | `ruff check`, `ruff format --check`, `mypy app/` |
| **Backend Test** | `uv run pytest` (with coverage report) |
| **Frontend Lint & Typecheck** | `npm run lint`, `tsc --noEmit` |
| **Frontend Test** | `npx vitest run` (Vitest) |

**`contract-test.yml`** — Soroban contract tests and release WASM build:
| Job | Commands |
|-----|----------|
| **Build WASM** | `cargo build --target wasm32-unknown-unknown --release` |
| **Run Unit Tests** | `cargo test` |
| **Check WASM size** | `wc -c` on the release WASM (warns above 64 KB) |

**`deploy-testnet.yml`** — Manual Testnet deployment (`workflow_dispatch`):
| Step | Commands |
|-----|----------|
| **Gate** | `cargo fmt --check`, `cargo clippy -D warnings`, `cargo test` |
| **Build** | `cargo build --target wasm32-unknown-unknown --release` |
| **Deploy** | `scripts/deploy_contract.sh` against `testnet` |
| **Smoke test** | `python -m tests.smoke_testnet` against the new contract ID |

Each run publishes a new contract ID (a deployment is permanent and never
replaces a previous instance) and reports it in the job summary. The smoke test
runs against that deployment, so a green job means the deployed contract
actually answered — not merely that a WASM upload succeeded.

**`release.yml`** — Tag-triggered release:
| Step | Commands |
|-----|----------|
| **Version guard** | tag must equal the version in `Cargo.toml`, `pyproject.toml`, and `package.json` |
| **Test** | `cargo test` |
| **Build** | `cargo build --target wasm32-unknown-unknown --release` |
| **Publish** | attaches `geoguard_ledger.wasm` and its `sha256sum` file to the release |

### 9.2 Quality Gates

All of the following must pass before a PR can be merged:
- All CI jobs pass (green build).
- Code coverage does not decrease (enforced by coverage thresholds in CI).
- At least one approving review from a maintainer.
- All conversations on the PR are resolved.

### 9.3 Deployment Pipeline

Deployment is manual by design: it publishes a permanent contract instance, so
it is an explicit act rather than a side effect of merging.

- **Testnet:** the `Deploy to Testnet` workflow, gated behind the `testnet`
  GitHub environment (where a required reviewer can be configured) and a funded
  `TESTNET_DEPLOYER_SECRET`. It deploys, then smoke tests the contract it just
  published, and reports the contract ID in its job summary.
- **Releases:** pushing a `v*` tag publishes the built WASM and its SHA-256, so a
  deployment can be tied to an exact artifact rather than a local build.
- **Drift detection:** `cd backend && python -m tests.smoke_testnet --read-only`
  verifies that a deployed contract still exposes the entry points the backend
  calls. It needs no key and spends no fees, so it can be run on demand or on a
  schedule.
- **Production:** Manual trigger for Mainnet deployment after audit sign-off.
- **Contract Upgrades:** Require multi-sig governance and a timelock period.

---

## 10. Observability & Monitoring

### 10.1 Structured Logging

All services use structured JSON logging with the following severity levels:

| Level | Use Case |
|-------|----------|
| `DEBUG` | Detailed diagnostic info (RPC request/response payloads, CSV parsing steps). |
| `INFO` | Normal operations (dataset processed, transaction submitted, TTL extended). |
| `WARNING` | Recoverable anomalies (RPC timeout on first attempt, high anomaly score detected). |
| `ERROR` | Failures requiring attention (transaction rejected, contract panic, DB connection lost). |

**Backend:** Configured via `LOG_LEVEL` env var (default: `INFO`). Use `structlog` or Python's built-in `logging` with JSON formatter.

### 10.2 Metrics (Phase 3+)

A `/metrics` endpoint (Prometheus-compatible, planned) exposes:

| Metric | Type | Description |
|--------|------|-------------|
| `geoguard_datasets_processed_total` | Counter | Total datasets processed by the backend. |
| `geoguard_transactions_submitted_total` | Counter | Total Soroban transactions submitted. |
| `geoguard_transaction_errors_total` | Counter | Failed transaction submissions (by error type). |
| `geoguard_anomaly_score_histogram` | Histogram | Distribution of anomaly scores across datasets. |
| `geoguard_soroban_rpc_latency_seconds` | Histogram | Soroban RPC response latency. |
| `geoguard_ttl_records_expiring_soon` | Gauge | Number of anchor records with TTL < 30 days remaining. |

**Available today:** the expiry gauges are exposed in JSON form at
`GET /api/v1/maintenance/ttl-status`, per entry kind — `roots` and `records`
blocks each carrying `due_for_renewal`, `past_recorded_expiry`,
`with_renewal_error`, `next_expiry_at` and `last_renewed_at`. Prometheus
exposition of the full table above is still planned.

**Alert on `past_recorded_expiry` above zero, or on `with_renewal_error`
growing, under either kind:** either means the renewal job has stopped keeping
up, and the failure is otherwise invisible until someone tries to verify a
dataset and is told it is not on-chain.

### 10.3 Alerting

**Critical alerts (Phase 3+):**
- Soroban RPC unreachable for > 5 minutes.
- Transaction failure rate exceeds 10% in a 15-minute window.
- Database connection pool exhausted.
- Records approaching TTL expiry (warning at 14 days, critical at 3 days).

---

## 11. Contribution Guidelines

### 11.1 How to Contribute

1. **Fork & Clone:** Fork the repo, clone locally.
2. **Pick an Issue:** Find a `good-first-issue` or `help-wanted` label, or open a discussion first for larger features.
3. **Branch:** `git checkout -b feat/your-feature-name` or `fix/issue-number`.
4. **Follow Conventions:**
   - **Rust:** `cargo fmt`, `cargo clippy`, `cargo test` must pass.
   - **Python:** `ruff` for linting/formatting, `mypy` for type checking, `pytest` for tests.
   - **TypeScript:** ESLint + Prettier, `tsc --noEmit` for type checking.
5. **Write Tests:** New features must include tests. Bug fixes should include a regression test.
6. **Update Docs:** If you add an endpoint, update `docs/api_reference.md`. If you change a contract function, update `contracts/README.md`.
7. **PR Template:** Use the provided PR template. Link the issue. Include screenshots for UI changes.

### 11.2 Development Setup (One-Command)

```bash
# Prerequisites: Docker, Rust, Python 3.11+, Node 18+
./scripts/setup_dev.sh
```

This script:
1. Creates a Python virtual environment and installs dependencies via `uv sync`.
2. Installs Node.js dependencies via `npm install`.
3. Builds the Soroban contract to WASM (`cargo build --target wasm32-unknown-unknown --release`).
4. Starts PostgreSQL via Docker Compose.
5. Runs database migrations (`uv run alembic upgrade head`).

### 11.3 Code Standards

| Language | Formatter | Linter | Type Checker | Test Runner |
|----------|-----------|--------|--------------|-------------|
| Rust (Soroban) | `cargo fmt` | `cargo clippy` | `cargo check` | `cargo test` |
| Python | `ruff format` | `ruff check` | `mypy` | `pytest` |
| TypeScript | Prettier | ESLint | `tsc --noEmit` | Vitest |

### 11.4 Commit Conventions

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(contract): add anchor_hash function
fix(backend): handle CSV with BOM characters
docs: update API reference for verify endpoint
test(frontend): add CsvDropzone unit tests
chore(ci): add Soroban contract test workflow
```

### 11.5 Communication

- **GitHub Issues:** Bug reports, feature requests, RFCs.
- **GitHub Discussions:** Q&A, ideas, community.
- **Weekly Community Call (proposed):** 30-min sync for active contributors.

---

## 12. Development Roadmap

### Phase 1: Foundation & Planning (Weeks 1–2) — ✅ COMPLETED

| Task | Deliverable |
|------|-------------|
| Finalize SPECIFICATION.md | Approved spec document. |
| Set up monorepo structure | Directory scaffolding, CI workflows. |
| Set up Soroban dev environment | `soroban-cli`, local RPC, Testnet account. |
| Contract design review | Community feedback on contract interface. |
| DB schema design | SQLAlchemy models, Alembic initial migration. |
| API schema design | OpenAPI spec for all v1 endpoints. |
| UI wireframes | Low-fidelity wireframes for all pages. |
| AI model selection | Evaluate Isolation Forest vs. LSTM autoencoder on sample geochemical data. |

### Phase 2: Smart Contract Development (Weeks 3–4) — ✅ COMPLETED

| Task | Deliverable |
|------|-------------|
| Implement `GeoGuardLedger` contract | `anchor_hash`, `verify_integrity`, all getters, `extend_ttl`, `transfer_admin`. ✅ |
| Write comprehensive unit tests | 8 tests covering initialization, anchoring, verification, error cases, admin transfer. ✅ |
| Deploy to Stellar Testnet | Contract built and ready for deployment. ⏳ (pending deployer key) |
| Gas cost benchmarking | Report on per-anchor costs. ✅ (estimated in §4.7) |
| Contract README | How to build, test, deploy, invoke. ⏳ |

### Phase 3: Backend API Development (Weeks 5–7) — 🚧 IN PROGRESS

| Task | Deliverable | Status |
|------|-------------|:---:|
| FastAPI project scaffold | App factory, config, CORS, lifespan. | ✅ |
| Database models + migrations | SQLAlchemy async models, session factory. | ✅ |
| SHA-256 hasher service | CSV canonicalization + hashing (fully implemented). | ✅ |
| AI anomaly detection service | Isolation Forest model, model versioning, scoring. | 🚧 Stubbed |
| Soroban RPC client | Transaction building, signing prep, submission, polling. | 🚧 Stubbed |
| All v1 endpoints | POST datasets, POST submit, GET datasets, GET dataset, POST verify, GET health (routers exist, logic stubbed). | 🚧 Stubbed |
| Integration tests | End-to-end test: CSV → hash → AI → Soroban tx. | ⏳ |
| Docker Compose | PostgreSQL + backend + frontend orchestration. | ✅ |
| API documentation | OpenAPI docs at `/docs`. | ✅ |

**Remaining Work (Phase 3):**
- Implement `anomaly.py` with a trained Isolation Forest model using scikit-learn.
- Implement `soroban.py` using `stellar-sdk` for transaction building and RPC submission.
- Wire the dataset endpoints to PostgreSQL via SQLAlchemy async sessions.
- Add `pytest` integration tests with mocked Soroban RPC.

### Phase 4: Frontend UI & End-to-End Integration (Weeks 8–10) — 🚧 SCAFFOLDED

| Task | Deliverable | Status |
|------|-------------|:---:|
| Vite + React scaffold | Project setup, routing, Tailwind. | ✅ |
| Freighter wallet integration | `useWallet` hook, `WalletContext`, `WalletConnector` component. | ✅ |
| Upload page | `CsvDropzone` with single-dataset and batch (Merkle root) anchoring modes. | ✅ |
| Submission workflow | `SubmissionStepper`: Upload → Preview → AI Report → Sign → Confirmed. | 🚧 Scaffolded |
| Dashboard page | Stats cards, recent submissions table. | 🚧 Scaffolded |
| Dataset list + detail pages | Table view, detail view with anomaly badge. | 🚧 Scaffolded |
| Verification page | Upload/input → verify → side-by-side result. | 🚧 Scaffolded |
| Settings page | Network selection, wallet info. | 🚧 Scaffolded |
| End-to-end tests | Full flow: CSV upload → verify on-chain. | ⏳ |
| Polish & accessibility | Loading states, error boundaries, keyboard nav, ARIA labels. | ⏳ |

**Remaining Work (Phase 4):**
- Implement all page components with full business logic (API calls, state management, error handling).
- Add Vitest component tests and Playwright E2E tests.
- Implement all UX states: loading spinners, error toasts, empty states, transaction pending animations.

### Phase 5: Batched Anchoring (Scale Hardening) — ✅ COMPLETED

| Task | Deliverable | Status |
|------|-------------|:---:|
| Merkle tree service | Deterministic tree construction and inclusion proofs (`app/services/merkle.py`). | ✅ |
| On-chain root anchoring | `anchor_root`, `get_root`, `verify_inclusion`, `get_batch_count`, `get_total_batches`, `extend_root_ttl`, `RootRecord`. | ✅ |
| Batch API | `POST /batches`, `POST /batches/{id}/submit`, `GET /batches`, `GET /batches/{id}`. | ✅ |
| Proof surfacing | `/verify` returns an `inclusion` block for batched datasets, with local and on-chain verdicts. | ✅ |
| Batch persistence | `batches` table plus `batch_id`, `merkle_root`, `leaf_index`, `merkle_proof` on `datasets`. | ✅ |
| Tests | Contract (Merkle), Merkle-service, batch-API, and frontend suites. | ✅ |
| Frontend batching | `BatchAnchorFlow` builds and anchors a batch from the upload page; `MerkleProof` displays the root and inclusion proof on the upload and verify pages; `/verify` accepts a linked `dataset_hash`; the dataset list and detail pages surface batch membership via `BatchBadge` and the stored proof path. | ✅ |
| TTL renewal | `app/services/ttl_renewal.py` selects anchored entries entering their renewal window and renews them through the operational account — batch roots via `extend_root_ttl`, standalone records via `extend_ttl`. `app/jobs/renew_ttl.py` runs one pass on a schedule; `GET /api/v1/maintenance/ttl-status` reports the backlog per kind. | ✅ |
| Record TTL on write | `anchor_hash` extends a new record to its full budget, so a standalone anchor is not archived at the network's minimum persistent-entry TTL. | ✅ |

**Remaining Work (Phase 5):**
- Renewal deadlines come from the contract's TTL budgets *as recorded in the database*, not from the ledger. Reading each entry's `liveUntilLedgerSeq` would remove that assumption entirely — and would also let the job confirm the ~180-day write-time bump against what the network actually grants.
- Batch listing and management UI — the API is ready and dataset pages now show membership, but there is no batch index or management page.

### Post-Launch

- **IPFS/Arweave integration** for decentralized raw data storage.
- **TTL Renewal Automation — delivered:** `app/jobs/renew_ttl.py` proactively renews batch roots (`extend_root_ttl`) and standalone records (`extend_ttl`) as they approach expiry, acting as an automated rent payer so researchers never lose query access to their proofs. It is a scheduled command rather than an in-process task, so multiple API replicas do not each run it; the calls are permissionless and idempotent, so overlapping runs never extend an entry twice. Batch roots are what make this tractable at scale: one renewal keeps an entire batch alive.
- **Batch-aware frontend:** Surface batch creation and Merkle proof display in the upload and verification UIs.
- **Researcher reputation system** (on-chain scores based on anomaly-free submissions).
- **Multi-model support** (pluggable AI backends).
- **Mobile-responsive audit view** for in-field verification.

---

## 13. Security Considerations

### 13.1 What's On-Chain vs. Off-Chain

| Data | On-Chain (Public) | Off-Chain (Backend DB) |
|------|:---:|:---:|
| Dataset hash (SHA-256) | ✓ | ✓ |
| Anomaly score | ✓ | ✓ |
| Model version | ✓ | ✓ |
| Timestamp | ✓ | ✓ |
| Submitter public key | ✓ | ✓ |
| Raw CSV content | ✗ | ✓ (or IPFS hash) |
| Per-row anomaly flags | ✗ | ✓ |
| Researcher email / real name | ✗ | ✓ |

### 13.2 Threat Model

| Threat | Mitigation |
|--------|------------|
| **Hash collision** | Use SHA-256. In later phases, upgrade to SHA-512 or BLAKE3 if needed. |
| **Replay attack** | Contract rejects duplicate hashes. Submit count tracked per address. |
| **Front-running** | Not applicable: no economic value in racing to anchor. |
| **Malicious CSV** | Backend validates CSV structure. AI model is sandboxed (no code execution). |
| **Private key leak** | Researcher keys managed by Freighter (browser extension). Backend never sees private keys. |
| **Contract upgrade attack** | Admin key is multi-sig in production. Upgrade path TBD (native Soroban upgrade vs. proxy pattern). |
| **Data exfiltration** | Raw data stays off-chain. Only hashes are public. Researchers should be aware that on-chain data is permanently public. |

### 13.3 Audit Recommendations

Before Mainnet deployment, the Soroban contract should undergo:
1. Internal code review by at least two developers.
2. Formal verification of the `anchor_hash` state machine (no double-anchor, no overwrite).
3. Third-party security audit (recommended: OtterSec, Trail of Bits, or Certora).

---

## 14. Open Questions & Future Work

1. **Storage Layer:** Should raw CSV data be stored in IPFS with the CID linked on-chain, or is local/centralized storage acceptable for v1? (Recommended: IPFS in Phase 3.)
2. **Authentication:** Should Phase 1 require API keys for the backend, or is it open to any researcher during the pilot? (Recommended: simple API keys for Phase 1, JWT/OAuth in Phase 3.)
3. **Network:** Testnet-only for Phase 1–4. Mainnet deployment timeline TBD — requires audit and community consensus.
4. **AI Model Training Data:** What sample geochemical datasets will be used to train the initial anomaly model? Synthetic data? Historical lab data?
5. **Gas Subsidy:** Should Green Analytics Labs subsidize gas fees for researchers during the pilot? This could be implemented as a fee-bump or sponsored transaction pattern on Stellar.
6. **Multi-Chain:** Are there requirements to support Ethereum or other chains in the future? The architecture is designed to be chain-agnostic at the backend level (soroban.py can become a pluggable adapter).
7. **Data Retention:** How long should off-chain metadata be retained? GDPR considerations for European researchers?

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **Anchoring** | The act of writing a cryptographic proof (hash) to an immutable blockchain ledger. |
| **Canonicalization** | Normalizing data (sorting, whitespace trimming) so that semantically identical CSVs produce the same hash. |
| **Freighter** | A browser extension wallet for the Stellar network (similar to MetaMask for Ethereum). |
| **Soroban** | Stellar's smart contract platform (Rust → WASM). |
| **XDR** | External Data Representation — Stellar's binary format for transactions. |
| **XLM** | Stellar Lumens — the native currency of the Stellar network. |

## Appendix B: References

- [Stellar Soroban Documentation](https://soroban.stellar.org/docs)
- [Freighter Wallet API](https://docs.freighter.app)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Stellar Expert Explorer (Testnet)](https://stellar.expert/explorer/testnet)
- [Apache 2.0 License](https://www.apache.org/licenses/LICENSE-2.0)
