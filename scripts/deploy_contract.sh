#!/usr/bin/env bash
# Deploy the GeoGuard Ledger Soroban contract to Stellar Testnet.
#
# Prerequisites:
#   - stellar CLI installed (v21+): npm install -g @stellar/stellar-cli
#   - DEPLOYER_SECRET env var set with a funded Testnet secret key
#   - Contract built with: stellar contract build --optimize
#
# Usage:
#   DEPLOYER_SECRET=S... ./scripts/deploy_contract.sh
#
# Output:
#   - Prints the deployed CONTRACT_ID
#   - Optionally writes it to backend/.env (pass --write-env)
#   - Optionally initializes the contract with an admin (pass --admin G...)
#
# Examples:
#   DEPLOYER_SECRET=S... ./scripts/deploy_contract.sh
#   DEPLOYER_SECRET=S... ./scripts/deploy_contract.sh --write-env
#   DEPLOYER_SECRET=S... ./scripts/deploy_contract.sh --admin GABC... --write-env

set -euo pipefail

# ── Argument parsing ──────────────────────────────────────────────

WRITE_ENV=false
ADMIN_ADDRESS=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --write-env) WRITE_ENV=true; shift ;;
        --admin) ADMIN_ADDRESS="$2"; shift 2 ;;
        *) echo "Unknown argument: $1"; exit 1 ;;
    esac
done

# ── Prerequisites check ───────────────────────────────────────────

if ! command -v stellar &>/dev/null; then
    echo "Error: 'stellar' CLI not found."
    echo "Install it: npm install -g @stellar/stellar-cli"
    echo "Or via Homebrew: brew install stellar/tools/stellar-cli"
    exit 1
fi

STELLAR_VERSION=$(stellar --version 2>/dev/null | head -1 || echo "unknown")
echo "stellar CLI: $STELLAR_VERSION"

# ── Paths ─────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Our contract uses wasm32v1-none target via stellar contract build
WASM_PATH="$PROJECT_ROOT/contracts/geoguard-ledger/target/wasm32v1-none/release/geoguard_ledger.wasm"

if [ ! -f "$WASM_PATH" ]; then
    echo "Error: WASM not found at $WASM_PATH"
    echo "Build it first:"
    echo "  cd contracts/geoguard-ledger && stellar contract build --optimize"
    exit 1
fi

if [ -z "${DEPLOYER_SECRET:-}" ]; then
    echo "Error: DEPLOYER_SECRET not set"
    echo "Usage: DEPLOYER_SECRET=S... ./scripts/deploy_contract.sh"
    exit 1
fi

# ── Deploy to Testnet ─────────────────────────────────────────────

echo "[1/2] Deploying to Testnet..."
CONTRACT_ID=$(stellar contract deploy \
    --wasm "$WASM_PATH" \
    --source "$DEPLOYER_SECRET" \
    --network testnet)

echo "       Contract ID: $CONTRACT_ID"

# ── Initialize (optional) ────────────────────────────────────────

if [ -n "$ADMIN_ADDRESS" ]; then
    echo "[2/2] Initializing contract with admin $ADMIN_ADDRESS..."
    stellar contract invoke \
        --id "$CONTRACT_ID" \
        --source "$DEPLOYER_SECRET" \
        --network testnet \
        -- initialize \
        --admin "$ADMIN_ADDRESS"
else
    echo "[2/2] Skipping initialization (no --admin flag)."
    echo "       Run later: stellar contract invoke --id $CONTRACT_ID --network testnet -- initialize --admin <ADMIN>"
fi

# ── Write to .env ─────────────────────────────────────────────────

if [ "$WRITE_ENV" = true ]; then
    ENV_FILE="$PROJECT_ROOT/backend/.env"
    if grep -q "^CONTRACT_ID=" "$ENV_FILE" 2>/dev/null; then
        sed -i.bak "s/^CONTRACT_ID=.*/CONTRACT_ID=$CONTRACT_ID/" "$ENV_FILE"
        rm -f "${ENV_FILE}.bak"
    else
        echo "CONTRACT_ID=$CONTRACT_ID" >> "$ENV_FILE"
    fi
    echo "       Written to $ENV_FILE"
fi

echo ""
echo "============================================"
echo " Deployment complete!"
echo ""
echo " CONTRACT_ID=$CONTRACT_ID"
echo ""
echo " Set it in backend/.env:"
echo "   CONTRACT_ID=$CONTRACT_ID"
echo ""
echo " Initialize (if not done above):"
echo "   stellar contract invoke \\"
echo "     --id $CONTRACT_ID \\"
echo "     --source <ADMIN_SECRET> \\"
echo "     --network testnet -- initialize --admin <ADMIN_PUBKEY>"
echo "============================================"
