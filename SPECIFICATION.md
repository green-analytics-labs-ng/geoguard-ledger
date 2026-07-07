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

1. **Hashing** raw geochemical data (CSV uploads) to produce a tamper-evident fingerprint.
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
    Researcher drags/drops a CSV file into the React frontend.
    Frontend reads the file client-side and shows a preview (first 10 rows).

Step 2: PREVIEW & CONFIRM
    Researcher reviews the data preview, selects columns for hashing
    (default: all numeric columns), and clicks "Submit for Anchoring."

Step 3: BACKEND PROCESSING (FastAPI)
    a. CSV is transmitted to POST /api/v1/datasets as multipart/form-data.
    b. Backend validates CSV structure (rows > 0, required columns present).
    c. Backend computes SHA-256 hash over the canonicalized CSV content.
       Canonicalization rules (critical for deterministic hashing):
       - RFC 4180-compliant CSV parsing with UTF-8 encoding (no BOM).
       - Line endings normalized to \n.
       - Numeric columns truncated to 6 decimal places.
       - Trailing whitespace stripped from all cells.
       - Rows sorted by their index in the original file.
       - Exactly these rules are published so third parties can reproduce hashes.
    d. Backend invokes AI anomaly detection model:
       - Input: numeric columns from the CSV.
       - Output: anomaly_score (0.0–1.0), anomaly_flags (list of row indices),
         model_version.
    e. Backend builds a Soroban transaction:
       - Invokes contract function: anchor_hash(hash, anomaly_score, model_version).
       - Sets fee, source account, network passphrase.
    f. Backend returns the unsigned transaction XDR, dataset UUID, hash,
       and anomaly report to the frontend.

Step 4: WALLET SIGNING (Freighter)
    a. Frontend passes the transaction XDR to Freighter wallet.
    b. Researcher reviews and approves the transaction in Freighter.
    c. Freighter returns the signed transaction XDR.

Step 5: SUBMIT & CONFIRM
    a. Frontend sends the signed XDR to POST /api/v1/datasets/:id/submit.
    b. Backend submits the signed transaction to the Soroban RPC endpoint.
    c. Backend polls for transaction status until SUCCESS or FAILED.
    d. On SUCCESS: Backend stores the Stellar transaction hash, ledger number,
       and updates dataset status to "anchored."
    e. Backend returns the confirmation with on-chain proof details.

Step 6: VERIFICATION DISPLAY
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
- **Effect:** Extends the Time-To-Live (TTL) of the `Record(dataset_hash)` Persistent ledger entry to `extend_to` (expressed as a ledger sequence number).
- **Rationale:** Stellar's state rent model requires periodic TTL renewal. This function allows the backend (or any third party) to proactively extend the lifespan of anchored records, keeping queries fast and free of archival-restoration overhead.

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
```

**Event Retention Note:** Standard Stellar RPC nodes only retain event history for a limited window (typically ~2 weeks). For long-term auditability, the backend must persist `Anchored` events into PostgreSQL as they are emitted. This ensures the system can reconstruct its full history even if all on-chain events have been pruned. For decentralized recovery, a Stellar data indexer (e.g., a custom Horizon listener) may be employed to mirror event history off-chain.

### 4.6 Error Handling

The contract defines five error variants for predictable error handling by clients (backend and frontend). These are surfaced as `Symbol` values in failed transaction result codes:

| Code | Variant | Description |
|:---:|---|-----------|
| 1 | `NotInitialized` | Contract has not been initialized (no `Admin` set). |
| 2 | `AlreadyInitialized` | `initialize()` called more than once. |
| 3 | `HashAlreadyAnchored` | Attempted to anchor a dataset hash that already exists on-chain. |
| 4 | `HashNotFound` | Attempted `extend_ttl()` on a non-existent hash. |
| 5 | `Unauthorized` | Caller lacks the required authorization (e.g., non-admin for `transfer_admin`). |

```rust
/// Defined in contracts/geoguard-ledger/src/errors.rs
pub enum Error {
    NotInitialized = 1,
    AlreadyInitialized = 2,
    HashAlreadyAnchored = 3,
    HashNotFound = 4,
    Unauthorized = 5,
}
```

Frontend and backend clients should parse these error codes from the Soroban transaction result to provide meaningful user feedback (e.g., "This dataset has already been anchored" versus "Network error — please try again").

### 4.7 Gas & Cost Model

- Each `anchor_hash` call stores ~100 bytes of data (32 + 4 + ~12 + 8 + 32).
- **State Rent & TTL:** Stellar Soroban charges ongoing rent for ledger entries. Each Persistent entry has a Time-To-Live (TTL) measured in ledgers (~5 seconds per ledger). When TTL expires, the entry is archived (recoverable for Persistent, permanently deleted for Temporary). Someone must periodically call `extend_ttl()` to keep records alive and queryable without archival-restoration overhead.
  - **Important:** TTL expiry is **not** a security mechanism — anyone can permissionlessly renew any entry. Validity logic (timestamps) lives inside the contract code, not in the TTL.
- Estimated cost per anchoring (Testnet, subject to change): ~0.5–1 XLM, plus ongoing rent of ~0.01–0.05 XLM/year per record.
- **Future:** Consider a "batching" function (`anchor_root`) that anchors a Merkle root instead of individual hashes. This collapses O(n) rent costs into O(1) by storing thousands of dataset proofs under a single Persistent key. Individual dataset verification is then performed off-chain using Merkle inclusion proofs against the on-chain root.

---

## 5. Backend API Specification (FastAPI)

### 5.1 Base URL

```
Development: http://localhost:8000/api/v1
```

### 5.2 Endpoints

#### `POST /api/v1/datasets`
Upload and process a new geochemical dataset.

**Request:**
```
Content-Type: multipart/form-data
  - file: CSV file (required)
  - researcher_id: string (optional, derived from auth token in later phases)
  - hash_columns: string[] (optional, columns to include in hash)
```

**Response (201 Created):**
```json
{
  "dataset_id": "uuid",
  "dataset_hash": "abc123...",
  "anomaly_report": {
    "score": 0.12,
    "flags": [42, 87],
    "model_version": "isoforest_v1",
    "summary": "12% anomaly probability. 2 rows flagged."
  },
  "unsigned_transaction_xdr": "AAAAAgAAA...",
  "created_at": "2026-07-05T12:00:00Z"
}
```

#### `POST /api/v1/datasets/{dataset_id}/submit`
Submit a researcher-signed transaction to the Stellar network.

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

#### `POST /api/v1/verify`
Verify a dataset against its on-chain proof.

**Request:**
```json
{
  "dataset_id": "uuid"         // Option A: look up by ID
  // OR
  "dataset_hash": "abc123...", // Option B: verify by hash directly
  "file": "..."                // Option C: re-upload CSV to re-hash and verify
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
  }
}
```

#### `GET /api/v1/health`
Health check endpoint. Returns `{"status": "ok", "soroban_rpc": "connected"}`.

### 5.3 Authentication & Authorization

**Phase 1 (Current):** The API is open. `researcher_id` is derived from the submitter's Stellar public key embedded in the signed transaction XDR. No additional API authentication is required during the pilot — trust is established cryptographically via the wallet signature on the transaction itself.

**Phase 2+ (Planned):** API key authentication via `X-API-Key` header, validated against a table of registered researchers. This prevents anonymous abuse of the CSV processing and AI inference endpoints without requiring a wallet signature for read-only operations.

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
| `/datasets` | `DatasetListPage` | Paginated table of all submitted datasets with status badges. |
| `/datasets/:id` | `DatasetDetailPage` | Full detail: hash, anomaly report, on-chain tx link, verify button. |
| `/verify` | `VerifyPage` | Upload or paste a hash to verify against the blockchain. |
| `/settings` | `SettingsPage` | Stellar network selection (Testnet/Mainnet), wallet connection. |

### 6.3 Key UI Components

| Component | Description |
|-----------|-------------|
| `CsvDropzone` | Drag-and-drop area with file validation (.csv only), row count display, preview table. |
| `WalletConnector` | "Connect Freighter" button. Shows connected address, network, and XLM balance. |
| `SubmissionWorkflow` | Stepper: Upload → Preview → AI Report → Sign → Confirmed. |
| `AnomalyBadge` | Color-coded badge (green < 5%, yellow 5–20%, red > 20%). |
| `TxExplorerLink` | Clickable link to Stellar Expert for a given transaction hash. |
| `VerificationResult` | Side-by-side comparison of on-chain record vs. local/computed values. |
| `DatasetTable` | Sortable table with columns: date, hash (truncated), anomaly score, status, actions. |

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
│   │   │   │   ├── datasets.py # Dataset endpoints
│   │   │   │   ├── verify.py   # Verification endpoints
│   │   │   │   └── health.py   # Health check
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── dataset.py      # SQLAlchemy model
│   │   │   └── schemas.py      # Pydantic request/response schemas
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── hasher.py       # SHA-256 hashing + canonicalization
│   │   │   ├── anomaly.py      # AI anomaly detection service
│   │   │   ├── soroban.py      # Soroban RPC client, tx building
│   │   │   └── storage.py      # IPFS integration (Phase 3)
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
│   │   │   └── verify.ts       # Verification API calls
│   │   ├── components/
│   │   │   ├── CsvDropzone.tsx
│   │   │   ├── WalletConnector.tsx
│   │   │   ├── SubmissionStepper.tsx
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
│   └── Dockerfile
│
├── docker-compose.yml          # Orchestrates backend + db + frontend
├── scripts/
│   ├── setup_dev.sh            # One-command dev environment setup
│   ├── deploy_contract.sh      # Deploy Soroban contract to Testnet
│   └── seed_db.py              # Seed database with sample datasets
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

**Run:** `cd contracts/geoguard-ledger && cargo test`

### 8.2 Backend Testing (Python)

**Framework:** `pytest` with `pytest-asyncio` for async endpoint tests.

**Test structure:**
```
backend/tests/
├── conftest.py          # Fixtures: test client, DB session, mocked Soroban RPC
├── test_datasets.py     # POST /datasets, submission, listing (13 tests)
├── test_verify.py       # POST /verify, hash comparison (6 tests)
├── e2e_full_api.py      # End-to-end API integration test
├── e2e_submission_flow.py # Full submission flow integration test
└── fixtures/
    └── sample.csv       # Deterministic test CSV
```

**Key patterns:**
- Use `httpx.AsyncClient` with the FastAPI `TestClient` for integration tests.
- Mock the Soroban RPC client (`soroban.py`) to avoid external network calls.
- Use an in-memory SQLite database (`aiosqlite`) for isolated test DB state.
- Test hash determinism: the same CSV must always produce the same SHA-256.
- Test canonicalization edge cases: BOM characters, `\r\n` line endings, trailing whitespace.

**Coverage targets:**
- All API endpoints: success responses, validation errors, and edge cases.
- Hasher service: identical CSVs produce identical hashes; modified CSVs produce different hashes.
- Anomaly service: valid CSV returns a properly structured anomaly report.

**Run:** `cd backend && uv run pytest`

### 8.3 Frontend Testing (TypeScript)

**Framework:** Vitest + React Testing Library.

**Key patterns:**
- Component tests: render components with mock API responses.
- Hook tests: test `useWallet`, `useDatasets`, `useVerify` in isolation with mocked Freighter API.
- Utility tests: CSV parsing, Stellar helper functions.

**Coverage targets:**
- All UI states: loading, success, error, empty.
- CsvDropzone: file validation (.csv only), size limits, preview rendering.
- WalletConnector: connected, disconnected, wrong network states.

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

**`contract-test.yml`** — Soroban-specific CI with WASM optimization:
| Job | Commands |
|-----|----------|
| **Build WASM** | `cargo build --target wasm32-unknown-unknown --release` |
| **Run Unit Tests** | `cargo test` |
| **Optimize WASM** | `soroban contract optimize` |

### 9.2 Quality Gates

All of the following must pass before a PR can be merged:
- All CI jobs pass (green build).
- Code coverage does not decrease (enforced by coverage thresholds in CI).
- At least one approving review from a maintainer.
- All conversations on the PR are resolved.

### 9.3 Deployment Pipeline (Future)

- **Staging:** Automatic deployment to Testnet on merge to `main`.
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
| Upload page | `CsvDropzone`, column selector, preview, submit button. | 🚧 Scaffolded |
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

### Post-Launch

- **IPFS/Arweave integration** for decentralized raw data storage.
- **Merkle Tree Batching (`anchor_root`):** A new contract function that anchors a Merkle root instead of individual hashes. This collapses O(n) rent costs into O(1) by storing thousands of dataset proofs under a single Persistent key. Individual verification is performed via Merkle inclusion proofs generated off-chain (backend or client-side) and validated against the on-chain root. This is essential for production scale.
- **TTL Renewal Automation:** A backend scheduler (Celery Beat) that proactively calls `extend_ttl()` on records approaching expiry, acting as an automated rent payer so researchers never lose query access to their proofs.
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
