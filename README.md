<!-- markdownlint-disable MD033 MD041 MD013 -->
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://img.shields.io/badge/GeoGuard-Ledger-7C3AED?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxyZWN0IHg9IjMiIHk9IjExIiB3aWR0aD0iMTgiIGhlaWdodD0iMTEiIHJ4PSIyIiByeT0iMiIvPjxwYXRoIGQ9Ik03IDExVjdhNSA1IDAgMCAxIDEwIDB2NCIvPjwvc3ZnPg==">
    <img src="https://img.shields.io/badge/GeoGuard-Ledger-7C3AED?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxyZWN0IHg9IjMiIHk9IjExIiB3aWR0aD0iMTgiIGhlaWdodD0iMTEiIHJ4PSIyIiByeT0iMiIvPjxwYXRoIGQ9Ik03IDExVjdhNSA1IDAgMCAxIDEwIDB2NCIvPjwvc3ZnPg==" alt="GeoGuard Ledger">
  </picture>
</p>

<p align="center"><strong>Immutable Integrity for Environmental Research</strong></p>

<p align="center">
  <a href="https://github.com/green-analytics-labs-ng/geoguard-ledger/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License: Apache 2.0"></a>
  <a href="https://github.com/green-analytics-labs-ng/geoguard-ledger/actions/workflows/ci.yml"><img src="https://github.com/green-analytics-labs-ng/geoguard-ledger/actions/workflows/ci.yml/badge.svg" alt="CI Status"></a>
  <a href="https://github.com/green-analytics-labs-ng/geoguard-ledger/actions/workflows/contract-test.yml"><img src="https://github.com/green-analytics-labs-ng/geoguard-ledger/actions/workflows/contract-test.yml/badge.svg" alt="Contract Tests"></a>
  <a href="https://www.rust-lang.org/"><img src="https://img.shields.io/badge/rust-1.70%2B-orange?logo=rust" alt="Rust 1.70+"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11%2B-blue?logo=python" alt="Python 3.11+"></a>
  <a href="https://nodejs.org/"><img src="https://img.shields.io/badge/node-18%2B-green?logo=node.js" alt="Node 18+"></a>
  <a href="CODE_OF_CONDUCT.md"><img src="https://img.shields.io/badge/contributor-covenant-ff69b4" alt="Contributor Covenant"></a>
</p>

<p align="center">
  <a href="https://github.com/green-analytics-labs-ng/geoguard-ledger/blob/main/SPECIFICATION.md#12-development-roadmap"><img src="https://img.shields.io/badge/status-active_development-7C3AED" alt="Status: Active Development"></a>
  <br><br>
  <b>A project by <a href="https://github.com/green-analytics-labs">Green Analytics Labs</a></b><br>
  <sub>Advancing sustainable, high-integrity geochemical research in Zaria, Kaduna State and beyond.</sub>
</p>

---

## Executive Summary

Environmental policy, public health interventions, and climate adaptation strategies depend on trustworthy geochemical data — yet raw datasets remain vulnerable to tampering, fabrication, and inadvertent corruption. Developed in **Zaria, Kaduna State, Nigeria**, **GeoGuard Ledger** addresses this by anchoring cryptographic integrity proofs directly onto the **Stellar blockchain**, producing an immutable, publicly verifiable chain of custody for every geochemical dataset. Using AI-powered anomaly detection, research-grade hashing, and decentralized smart contracts, GeoGuard ensures that the data informing our planet's most critical decisions — from groundwater safety assessments to climate adaptation planning — remains beyond reproach.

---

## Key Features

### 🔬 Research-Grade Integrity

- **Deterministic SHA-256 Hashing** — CSV data is canonicalized (RFC 4180, UTF-8 normalization, numeric truncation, sorted rows) before hashing, ensuring any third party can re-compute and verify the exact same fingerprint.
- **Tamper-Evident Proofs** — Once anchored, any alteration to the source data — even a single decimal place — produces a different hash, immediately exposing tampering.

### 🤖 AI Anomaly Detection

- **Isolation Forest Model** — Unsupervised machine learning flags rows that deviate statistically from the expected geochemical profile, detecting potential fabrication, instrument drift, or sampling errors.
- **Interpretable Scoring** — Each dataset receives an anomaly probability (0.0–1.0) with per-row flags and a human-readable summary. Color-coded thresholds (green: &lt;5%, yellow: 5–20%, red: &gt;20%) guide researcher review.
- **Multi-Model Ready** — Architecture supports pluggable backends (LSTM autoencoders, One-Class SVM) for domain-specific detection needs.

### ⛓️ Blockchain Anchoring (Soroban / Stellar)

- **Immutable On-Chain Records** — Dataset hashes, anomaly scores, model versions, timestamps, and submitter identities are permanently stored on the Stellar blockchain via Soroban smart contracts written in Rust.
- **Gas-Efficient Design** — Stellar's state rent model and low transaction fees make per-dataset anchoring economically viable at scale. Future Merkle tree batching will collapse O(n) rent costs into O(1).
- **Permissionless Verification** — Any third party — journal editor, regulator, fellow researcher — can verify a dataset's authenticity by calling the contract's `verify_integrity()` read-only function without gas costs or special permissions.

### 🔐 Privacy-Preserving Architecture

- **Only Hashes On-Chain** — Raw geochemical data stays off-chain (local storage or IPFS in later phases). Sensitive field measurements are never publicly exposed.
- **Client-Side Signing** — Transaction signing happens exclusively in the researcher's Freighter browser wallet. The backend never sees — and cannot leak — private keys.

### 🧪 Built for Open Science

- **Fully Open Source** — Apache 2.0 licensed. Researchers can inspect, modify, and extend every layer of the stack.
- **Reproducible Verification** — Published canonicalization rules allow independent re-hashing, making data integrity claims falsifiable and auditable.
- **Modular Architecture** — Swap the AI model, hash algorithm, or blockchain layer without rewriting the entire system.

---

## Architecture

```mermaid
flowchart TB
    subgraph Researcher["🔬 Researcher"]
        CSV["📄 CSV Geochemical Data<br/>(pH, conductivity, ions, etc.)"]
    end

    subgraph Frontend["🖥️ React Frontend"]
        Upload["CsvDropzone<br/>+ Preview"]
        Wallet["Freighter Wallet<br/>Sign Transaction"]
        Dashboard["Dashboard<br/>+ Verification UI"]
    end

    subgraph Backend["⚙️ Python FastAPI Backend"]
        Parser["CSV Parser<br/>+ Validator"]
        Hasher["SHA-256 Hasher<br/>Canonicalization Engine"]
        AI["AI Anomaly Detector<br/>Isolation Forest"]
        TxBuilder["Soroban TX Builder<br/>XDR Construction"]
    end

    subgraph Storage["💾 Data Layer"]
        PG[("PostgreSQL<br/>Metadata & Job State")]
        IPFS[("IPFS / Arweave<br/>Raw Data<br/>(🔮 Post-Launch)")]
    end

    subgraph Blockchain["⛓️ Stellar Blockchain"]
        RPC["Soroban RPC<br/>Testnet / Mainnet"]
        Contract["GeoGuardLedger<br/>Smart Contract<br/>(Rust / WASM)"]
    end

    subgraph Verification["✅ Third-Party Audit"]
        Auditor["Journal Editor<br/>Regulator<br/>Peer Researcher"]
    end

    CSV --> Upload
    Upload --> Parser
    Parser --> Hasher
    Parser --> AI
    Hasher --> TxBuilder
    AI --> TxBuilder
    TxBuilder -->|"Unsigned XDR"| Wallet
    Wallet -->|"Signed XDR"| TxBuilder
    TxBuilder -->|"Submit TX"| RPC
    RPC --> Contract
    Contract -->|"anchor_hash()"| Contract
    TxBuilder --> PG
    Upload --> Dashboard
    Dashboard -->|"verify_integrity()"| Contract

    Auditor -->|"Upload CSV / Paste Hash"| Dashboard
    Dashboard -->|"Re-hash & Verify"| Contract
    Contract -->|"Match / No Match"| Dashboard
    Dashboard -->|"✓ Verified / ✗ Tampered"| Auditor

    style Contract fill:#7C3AED,stroke:#5B21B6,color:#fff
    style AI fill:#059669,stroke:#047857,color:#fff
    style Hasher fill:#2563EB,stroke:#1D4ED8,color:#fff
    style Researcher fill:#F59E0B,stroke:#D97706,color:#fff
    style Auditor fill:#EC4899,stroke:#DB2777,color:#fff
```

<p align="center"><em>Data flows from CSV ingestion through AI anomaly detection and canonicalization, with integrity proofs anchored immutably on Stellar for independent third-party verification.</em></p>

---

## Getting Started

### Prerequisites

| Tool | Minimum Version | Purpose |
| :--- | :------------: | :------ |
| [Docker](https://docs.docker.com/get-docker/) | 24+ | Containerized PostgreSQL, backend, and frontend services |
| [Rust](https://rustup.rs/) | 1.70+ | Soroban smart contract compilation |
| [Python](https://www.python.org/downloads/) | 3.11+ | Backend API and AI model inference |
| [Node.js](https://nodejs.org/) | 18+ | React frontend development |
| [Freighter Wallet](https://www.freighter.app/) | Latest | Stellar browser extension for transaction signing |

### Quick Start (One Command)

```bash
# Clone the repository
git clone https://github.com/green-analytics-labs-ng/geoguard-ledger.git
cd geoguard-ledger

# Run the automated setup script
./scripts/setup_dev.sh
```

This script installs all dependencies, builds the Soroban contract to WASM, starts PostgreSQL via Docker, runs database migrations, and prepares the development environment. When it completes, you'll have:

- **Backend API:** [http://localhost:8000/docs](http://localhost:8000/docs) (interactive OpenAPI docs)
- **Frontend:** [http://localhost:5173](http://localhost:5173)
- **Database:** `postgresql://geoguard:geoguard_dev@localhost:5432/geoguard_ledger`

### Manual Setup (Step-by-Step)

If you prefer to set up each component individually:

<details>
<summary><strong>1. Backend (FastAPI)</strong></summary>

<br>

```bash
cd backend

# Create virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install uv
uv sync

# Start PostgreSQL
docker compose up -d db

# Run database migrations
uv run alembic upgrade head

# Start the API server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

</details>

<details>
<summary><strong>2. Smart Contract (Soroban)</strong></summary>

<br>

```bash
cd contracts/geoguard-ledger

# Build the contract
cargo build --target wasm32-unknown-unknown --release

# Run contract unit tests
cargo test --verbose

# Lint
cargo fmt --all -- --check
cargo clippy --target wasm32-unknown-unknown -- -D warnings
```

</details>

<details>
<summary><strong>3. Frontend (React + TypeScript)</strong></summary>

<br>

```bash
cd frontend

# Install dependencies
npm install

# Start the development server
npm run dev
```

</details>

<details>
<summary><strong>4. All Services (Docker Compose)</strong></summary>

<br>

```bash
# Start everything at once
docker compose up

# Or in detached mode
docker compose up -d
```

</details>

### Deploy the Smart Contract to Testnet

```bash
# See contracts/README.md for full deployment instructions
soroban contract deploy \
  --wasm target/wasm32-unknown-unknown/release/geoguard_ledger.wasm \
  --source <YOUR_SECRET_KEY> \
  --network testnet
```

---

## Project Structure

```text
geoguard-ledger/
├── contracts/                  # Soroban smart contracts (Rust → WASM)
│   └── geoguard-ledger/
│       ├── src/
│       │   ├── lib.rs          # Contract entry point
│       │   ├── storage.rs      # Persistent storage logic
│       │   ├── types.rs        # AnchorRecord, events
│       │   ├── errors.rs       # Contract-specific error variants
│       │   └── test.rs         # 11 comprehensive unit tests
│       └── Makefile            # Build, test, deploy targets
│
├── backend/                    # FastAPI backend (Python)
│   └── app/
│       ├── main.py             # App factory, CORS, lifespan
│       ├── config.py           # Environment-based configuration
│       ├── api/v1/             # REST endpoints (datasets, verify, health)
│       ├── models/             # SQLAlchemy models + Pydantic schemas
│       ├── services/           # Hasher, AI anomaly detector, Soroban client
│       ├── db/                 # Async SQLAlchemy session management
│       └── core/               # Security, custom exceptions
│
├── frontend/                   # React frontend (TypeScript + Tailwind)
│   └── src/
│       ├── pages/              # Dashboard, Upload, Verify, Settings
│       ├── components/         # CsvDropzone, WalletConnector, AnomalyBadge
│       ├── hooks/              # useWallet, useDatasets, useVerify
│       ├── context/            # WalletContext (Freighter state)
│       └── api/                # Typed API client layer
│
├── docs/                       # Architecture decisions, AI model guide
├── scripts/                    # setup_dev.sh, deploy_contract.sh, seed_db.py
├── docker-compose.yml          # Multi-service orchestration
├── SPECIFICATION.md            # Full technical specification
└── LICENSE
```

---

## Contributing

GeoGuard Ledger thrives on interdisciplinary collaboration. We welcome contributions from:

- **Geochemists & Environmental Scientists** — domain expertise, test datasets, validation of anomaly detection heuristics
- **Blockchain Engineers** — smart contract audits, gas optimizations, multi-chain expansion (Ethereum, Solana adapters)
- **Machine Learning Researchers** — new anomaly detection models, model evaluation frameworks, benchmark datasets
- **Frontend Developers** — accessibility improvements, mobile-responsive audit views, data visualization
- **Technical Writers** — documentation, tutorials, research publications

### How to Get Involved

1. **Read** [`CONTRIBUTING.md`](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md).
2. **Browse** [open issues](https://github.com/green-analytics-labs-ng/geoguard-ledger/issues) — look for `good-first-issue` or `help-wanted` labels.
3. **Discuss** larger ideas in [GitHub Discussions](https://github.com/green-analytics-labs-ng/geoguard-ledger/discussions) before coding.
4. **Fork, branch, and PR** — we follow [Conventional Commits](https://www.conventionalcommits.org/) and require tests for new features.

| Language | Formatter | Linter | Type Checker | Tests |
| :------- | :-------- | :----- | :----------: | :---- |
| Rust (Soroban) | `cargo fmt` | `cargo clippy` | ✓ | `cargo test` |
| Python | `ruff format` | `ruff check` | `mypy` | `pytest` |
| TypeScript | Prettier | ESLint | `tsc --noEmit` | Vitest |

---

## Academic Integrity & Citation

GeoGuard Ledger is built on the principles of **Open Science** and **Research Reproducibility**:

- **Falsifiability** — Every integrity claim is independently verifiable. Published canonicalization rules allow any third party to re-hash a dataset and compare against the on-chain proof. There is no central authority to trust.
- **Transparency** — All source code, model architectures, hashing algorithms, and canonicalization procedures are publicly documented and open-source. Nothing is hidden behind proprietary black boxes.
- **Persistence** — Blockchain-anchored proofs are immutable and recoverable. Even if Stellar ledger entries expire, Persistent storage semantics ensure they can be restored rather than permanently destroyed.
- **Privacy** — Raw data remains off-chain. Only cryptographic hashes — which cannot be reversed to reconstruct the original data — are made public. Researchers retain control over access to their field measurements.

### Suggested Citation

If you use GeoGuard Ledger in your research, please cite:

> Green Analytics Labs. *GeoGuard Ledger: Immutable Integrity for Environmental Research*. Version 0.2.0. Zaria, Kaduna State, Nigeria. [https://github.com/green-analytics-labs-ng/geoguard-ledger](https://github.com/green-analytics-labs-ng/geoguard-ledger)

```bibtex
@software{geoguard_ledger_2026,
  author       = {{Green Analytics Labs}},
  title        = {{GeoGuard Ledger}: Immutable Integrity for Environmental Research},
  year         = {2026},
  version      = {0.2.0},
  publisher    = {Green Analytics Labs},
  address      = {Zaria, Kaduna State, Nigeria},
  url          = {https://github.com/green-analytics-labs-ng/geoguard-ledger},
  note         = {Open-source research integrity system for geochemical data}
}
```

---

## License

GeoGuard Ledger is released under the [Apache License, Version 2.0](LICENSE).

```text
Copyright 2026 Green Analytics Labs

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

---

<p align="center">
  <sub>Built with 🔬 by <strong>Green Analytics Labs</strong> — Advancing geochemical research integrity, one hash at a time.</sub>
</p>
