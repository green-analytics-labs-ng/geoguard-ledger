#!/usr/bin/env bash
# One-command development environment setup for GeoGuard Ledger.
# Prerequisites: Docker, Rust, Python 3.11+, Node 18+

set -euo pipefail

echo "========================================="
echo " GeoGuard Ledger — Dev Environment Setup"
echo "========================================="

# 1. Install Python deps
echo "[1/5] Installing Python dependencies..."
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install uv
uv sync
deactivate
cd ..

# 2. Install Node deps
echo "[2/5] Installing Node dependencies..."
cd frontend
npm install
cd ..

# 3. Build Soroban contract
echo "[3/5] Building Soroban contract..."
cd contracts/geoguard-ledger
cargo build --target wasm32-unknown-unknown --release
cd ../..

# 4. Start PostgreSQL + backend + frontend via Docker
echo "[4/5] Starting services via Docker Compose..."
docker compose up -d db

# 5. Run database migrations
echo "[5/5] Running database migrations..."
cd backend
source .venv/bin/activate
uv run alembic upgrade head
deactivate
cd ..

echo ""
echo "========================================="
echo " Setup complete!"
echo ""
echo " Backend:  http://localhost:8000/docs"
echo " Frontend: http://localhost:5173"
echo " Database: postgresql://geoguard:geoguard_dev@localhost:5432/geoguard_ledger"
echo ""
echo " To start all services: docker compose up"
echo "========================================="
