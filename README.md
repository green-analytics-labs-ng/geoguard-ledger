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
- **Merkle Batch Anchoring** — Datasets can be committed under a single Merkle root, collapsing O(n) on-chain entries (and their rent obligations) into O(1). Each dataset keeps an inclusion proof that any third party can verify against the anchored root with the contract's `verify_inclusion()`, and renewing one root keeps an entire batch alive.
- **Automated TTL Renewal** — Anchors are Persistent ledger entries, so Soroban archives them once their rent runs out and verification stops answering: every dataset in a batch for a root, one dataset for a standalone record. Both are written with a ~180-day TTL and renewed by a scheduled job before that runs out, and `GET /api/v1/maintenance/ttl-status` reports the backlog per kind, so a stalled renewal is visible instead of silent.
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

# From the project root, start PostgreSQL
cd ..
docker compose up -d db
cd backend

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

Deploying publishes a permanent contract instance, so it is an explicit act
rather than something that happens on merge. From a local checkout:

```bash
cd contracts/geoguard-ledger
cargo build --target wasm32-unknown-unknown --release
cd ../..
DEPLOYER_SECRET=S... ./scripts/deploy_contract.sh --admin G... --write-env
```

Or run the **Deploy to Testnet** workflow from the Actions tab: it re-runs the
contract's gates, builds the WASM, deploys, and smoke tests the result.

A deployment is only useful if it exposes what the backend calls, and a contract
deployed before a feature existed keeps answering for the functions it has. Check
any deployment (no key, no fees):

```bash
cd backend && CONTRACT_ID=C... uv run python -m tests.smoke_testnet --read-only
```

See [docs/deployment.md](docs/deployment.md) for the full runbook — secrets,
initialization, releases, and what to do when a deployment has drifted.

### Keep Anchored Entries Alive

Anchors expire. They are Persistent ledger entries with a finite TTL (~180 days
from anchoring), and once one is archived the datasets it covers stop verifying —
every dataset in a batch for a batch root, one dataset for a standalone record.
Renewal is what keeps the ledger's promise true, and it is the one job that
spends real fees — so it is off until you arm it:

```bash
cd backend
export TTL_RENEWAL_ENABLED=true
export TTL_RENEWAL_SIGNER_SECRET=<funded operational account secret>

python -m app.jobs.renew_ttl --dry-run   # list what would be renewed
python -m app.jobs.renew_ttl             # renew for real
```

Run it on a schedule — cron, a systemd timer, or a Kubernetes CronJob. It is safe
to run repeatedly: renewing an entry records a new deadline that moves it out of
the window, so the next run skips it. Two overlapping runs may both attempt the
same entry — the contract treats the second as a no-op, so nothing is extended
twice, though that attempt still pays a transaction fee. It exits non-zero when a
renewal fails, and records the failure on the entry's row, so your scheduler can
alert.

The renewal account only ever pushes an expiry out — it cannot alter, forge, or
delete a record. It is deliberately not the researcher's key: unlike anchoring,
renewal is a state-changing call, so the backend signs it with this dedicated
"rent payer" account.

One caveat worth knowing: the deadlines the job plans around are recorded when
an entry is anchored or renewed, derived from the contract's TTL budgets — they
are not read back from the ledger. If those budgets ever change, `ttl-status`
keeps reporting the stale ones, which is why it is worth watching rather than
trusting.

---

## Project Structure

```text
geoguard-ledger/
├── contracts/                  # Soroban smart contracts (Rust → WASM)
│   └── geoguard-ledger/
│       ├── src/
│       │   ├── lib.rs          # Contract entry point
│       │   ├── storage.rs      # Persistent storage logic
│       │   ├── merkle.rs       # Deterministic Merkle leaf/node hashing
│       │   ├── types.rs        # AnchorRecord, RootRecord, events
│       │   ├── errors.rs       # Contract-specific error variants
│       │   └── test.rs         # Comprehensive unit tests
│       └── Makefile            # Build, test, deploy targets
│
├── backend/                    # FastAPI backend (Python)
│   ├── app/
│   │   ├── main.py             # App factory, CORS, lifespan
│   │   ├── config.py           # Environment-based configuration
│   │   ├── api/v1/             # REST endpoints (datasets, batches, verify, health)
│   │   ├── models/             # SQLAlchemy models + Pydantic schemas
│   │   ├── services/           # Hasher, Merkle proofs, TTL renewal, AI detector, Soroban client
│   │   ├── jobs/               # Scheduled jobs (TTL renewal)
│   │   ├── db/                 # Async SQLAlchemy session management
│   │   └── core/               # Security, custom exceptions
│   └── tests/                  # Unit suites, plus smoke_testnet.py for live Testnet checks
│
├── frontend/                   # React frontend (TypeScript + Tailwind)
│   ├── src/
│   │   ├── pages/              # Dashboard, Upload, Verify, Settings
│   │   ├── components/         # CsvDropzone, BatchAnchorFlow, MerkleProof, BatchBadge, AnomalyBadge
│   │   ├── hooks/              # useWallet, useDatasets, useVerify
│   │   ├── context/            # WalletContext (Freighter state)
│   │   └── api/                # Typed API client layer
│   └── tests/                  # Vitest + React Testing Library tests
│
├── docs/                       # Architecture, API reference, AI model, deployment runbook
├── .github/workflows/          # ci.yml, contract-test.yml, deploy-testnet.yml, release.yml
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
