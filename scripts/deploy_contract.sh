#!/usr/bin/env bash
# Deploy the GeoGuard Ledger Soroban contract to Stellar Testnet (or any
# configured network).
#
# Prerequisites:
#   - stellar CLI installed, v25.2.0 or newer:
#       curl -fsSL https://github.com/stellar/stellar-cli/raw/main/install.sh | sh
#     (or: brew install stellar-cli / cargo install --locked stellar-cli --features opt)
#     v25.2.0 is the floor because building the contract requires it, not because
#     deploying does: soroban-sdk 28 refuses to compile for a wasm target unless
#     the build system declares that it shakes the contract spec, and only this
#     CLI does that. An already-built WASM still deploys on an older one.
#   - DEPLOYER_SECRET env var set with a funded secret key (S...)
#   - Contract built: cd contracts/geoguard-ledger && stellar contract build
#
# Usage:
#   DEPLOYER_SECRET=S... ./scripts/deploy_contract.sh
#
# Options:
#   --admin G...            Initialize the contract with this admin address.
#                           Omitted: the contract is deployed uninitialized.
#   --write-env             Write CONTRACT_ID into backend/.env.
#   --contract-id-out FILE  Write the new contract ID to FILE. Used by CI to
#                           pass the ID to the smoke test; written as soon as
#                           the deploy succeeds, before initialization.
#   --network NAME          Network to deploy to (default: testnet).
#   --wasm PATH             WASM file to deploy. Defaults to the `stellar
#                           contract build` output (see WASM_PATH below).
#   -h, --help              Show this help.
#
# Environment:
#   DEPLOYER_SECRET  Funded secret key that pays for the deployment. Required.
#   NETWORK          Same as --network.
#   WASM_PATH        Same as --wasm.
#
# Examples:
#   DEPLOYER_SECRET=S... ./scripts/deploy_contract.sh
#   DEPLOYER_SECRET=S... ./scripts/deploy_contract.sh --write-env
#   DEPLOYER_SECRET=S... ./scripts/deploy_contract.sh --admin GABC... --write-env

set -euo pipefail

# ── Argument parsing ──────────────────────────────────────────────

WRITE_ENV=false
ADMIN_ADDRESS=""
CONTRACT_ID_OUT=""
NETWORK="${NETWORK:-testnet}"
WASM_PATH="${WASM_PATH:-}"

usage() {
    sed -n '2,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --write-env) WRITE_ENV=true; shift ;;
        --admin) ADMIN_ADDRESS="${2:-}"; shift 2 ;;
        --contract-id-out) CONTRACT_ID_OUT="${2:-}"; shift 2 ;;
        --network) NETWORK="${2:-}"; shift 2 ;;
        --wasm) WASM_PATH="${2:-}"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; usage >&2; exit 1 ;;
    esac
done

if [[ -n "$ADMIN_ADDRESS" && ! "$ADMIN_ADDRESS" =~ ^G[A-Z2-7]{55}$ ]]; then
    echo "Error: --admin must be a Stellar public key (G..., 56 chars), got: $ADMIN_ADDRESS" >&2
    exit 1
fi

# ── Paths ─────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# The path `stellar contract build` writes, which is also what the repository's
# CI and release workflows produce. It is the only supported build now: a bare
# `cargo build --target ...wasm...` is refused by soroban-sdk 28's build script,
# so there is no cargo path to fall back to. Pass --wasm (or WASM_PATH) to deploy
# something built elsewhere.
if [[ -z "$WASM_PATH" ]]; then
    WASM_PATH="$PROJECT_ROOT/contracts/geoguard-ledger/target/wasm32v1-none/release/geoguard_ledger.wasm"
fi

# ── Prerequisites check ───────────────────────────────────────────

if ! command -v stellar &>/dev/null; then
    {
        echo "Error: 'stellar' CLI not found."
        echo "Install it with:"
        echo "  curl -fsSL https://github.com/stellar/stellar-cli/raw/main/install.sh | sh"
        echo "  # or"
        echo "  brew install stellar-cli"
        echo "  # or"
        echo "  cargo install --locked stellar-cli --features opt"
    } >&2
    exit 1
fi

echo "stellar CLI: $(stellar --version 2>/dev/null | head -1 || echo unknown)"
echo "network:     $NETWORK"

if [[ ! -f "$WASM_PATH" ]]; then
    {
        echo "Error: WASM not found at $WASM_PATH"
        echo "Build it first:"
        echo "  cd contracts/geoguard-ledger && stellar contract build"
    } >&2
    exit 1
fi

if [[ -z "${DEPLOYER_SECRET:-}" ]]; then
    {
        echo "Error: DEPLOYER_SECRET not set."
        echo "Usage: DEPLOYER_SECRET=S... $(basename "${BASH_SOURCE[0]}")"
    } >&2
    exit 1
fi

echo "wasm:        $WASM_PATH ($(wc -c < "$WASM_PATH") bytes)"

# ── Deploy ────────────────────────────────────────────────────────

echo "[1/3] Deploying to $NETWORK..."

# Capture stdout only. The CLI writes progress and emoji to stderr, so stdout
# holds the contract ID; extracting it explicitly means a changed output format
# fails here instead of silently writing a wrong CONTRACT_ID downstream.
DEPLOY_STDOUT=$(stellar contract deploy \
    --wasm "$WASM_PATH" \
    --source-account "$DEPLOYER_SECRET" \
    --network "$NETWORK")

CONTRACT_ID=$(printf '%s\n' "$DEPLOY_STDOUT" | grep -oE 'C[A-Z2-7]{55}' | tail -n1 || true)

if [[ -z "$CONTRACT_ID" ]]; then
    {
        echo "Error: no contract ID found in the deploy output."
        echo "Raw output was:"
        printf '%s\n' "$DEPLOY_STDOUT"
    } >&2
    exit 1
fi

echo "      Contract ID: $CONTRACT_ID"

# Written before initialization so a failed initialize still leaves the operator
# (and CI) with the ID of the contract that is now live.
if [[ -n "$CONTRACT_ID_OUT" ]]; then
    mkdir -p "$(dirname "$CONTRACT_ID_OUT")"
    printf '%s\n' "$CONTRACT_ID" > "$CONTRACT_ID_OUT"
    echo "      ID written to $CONTRACT_ID_OUT"
fi

# ── Initialize (optional) ─────────────────────────────────────────

if [[ -n "$ADMIN_ADDRESS" ]]; then
    echo "[2/3] Initializing with admin $ADMIN_ADDRESS..."

    if ! stellar contract invoke \
        --id "$CONTRACT_ID" \
        --source-account "$DEPLOYER_SECRET" \
        --network "$NETWORK" \
        -- initialize \
        --admin "$ADMIN_ADDRESS"; then
        {
            echo ""
            echo "Error: initialize failed. The contract is deployed at $CONTRACT_ID"
            echo "but has no admin, so anchoring will return NotInitialized."
            echo "A likely cause is AlreadyInitialized on a redeploy; check with:"
            echo "  stellar contract invoke --id $CONTRACT_ID --network $NETWORK -- get_total_anchored"
        } >&2
        exit 1
    fi
else
    echo "[2/3] Skipping initialization (no --admin flag)."
    echo "      Run later: stellar contract invoke --id $CONTRACT_ID --source-account <SECRET> \\"
    echo "                   --network $NETWORK -- initialize --admin <ADMIN_PUBLIC_KEY>"
fi

# ── Write to .env (optional) ──────────────────────────────────────

if [[ "$WRITE_ENV" = true ]]; then
    echo "[3/3] Writing CONTRACT_ID to backend/.env..."
    ENV_FILE="$PROJECT_ROOT/backend/.env"
    touch "$ENV_FILE"
    if grep -q "^CONTRACT_ID=" "$ENV_FILE"; then
        sed -i.bak "s|^CONTRACT_ID=.*|CONTRACT_ID=$CONTRACT_ID|" "$ENV_FILE"
        rm -f "${ENV_FILE}.bak"
    else
        printf 'CONTRACT_ID=%s\n' "$CONTRACT_ID" >> "$ENV_FILE"
    fi
else
    echo "[3/3] Not writing backend/.env (pass --write-env to update it)."
fi

# ── Summary ───────────────────────────────────────────────────────

echo ""
echo "============================================"
echo " Deployment complete"
echo ""
echo " CONTRACT_ID=$CONTRACT_ID"
echo ""
echo " Verify it with the smoke test:"
echo "   cd backend && CONTRACT_ID=$CONTRACT_ID uv run python -m tests.smoke_testnet --read-only"
echo "============================================"
