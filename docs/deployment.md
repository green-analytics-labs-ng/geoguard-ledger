# GeoGuard Ledger — Deployment Runbook

How a contract gets onto Testnet, how a release is cut, and how to tell whether
the deployed contract is still the one the backend expects.

## What deploying means here

A Soroban deployment publishes a **new, permanent contract instance** with a new
contract ID. It does not upgrade a previous instance, and it cannot be undone.
Datasets anchored against an earlier instance stay bound to it — their records
are in that contract's storage and nothing will migrate them.

The consequence worth internalising: **a deployment that has drifted from this
source is a real problem, not a cosmetic one.** A contract deployed before a
feature existed still answers for the functions it has, and calls to functions it
lacks fail at runtime. That is why every deployment is followed by a live smoke
test, and why re-checking a deployment is a one-command operation that needs no
key.

## Prerequisites

| Tool | Why |
|---|---|
| Rust + the `wasm32-unknown-unknown` target | Builds the contract |
| `stellar` CLI v21+ | Deploys and invokes |
| A funded Testnet account | Pays for the deployment and its transactions |

```bash
rustup target add wasm32-unknown-unknown
curl -fsSL https://github.com/stellar/stellar-cli/raw/main/install.sh | sh
```

Fund a Testnet account with [Friendbot](https://laboratory.stellar.org/#account-creator?network=testnet),
either for a key you generate (`stellar keys generate deployer --network testnet --fund`)
or for an address you already hold.

## Deploy locally

```bash
cd contracts/geoguard-ledger
cargo build --target wasm32-unknown-unknown --release
cd ../..

DEPLOYER_SECRET=S... ./scripts/deploy_contract.sh --admin G... --write-env
```

| Flag | Effect |
|---|---|
| *(none)* | Deploy only. The contract has no admin, so anchoring returns `NotInitialized`. |
| `--admin G...` | Initialize the contract with this admin right after deploying. |
| `--write-env` | Write `CONTRACT_ID` into `backend/.env`. |
| `--contract-id-out FILE` | Write the new contract ID to `FILE` (used by CI to hand the ID to the smoke test). |
| `--network NAME` | Deploy somewhere other than Testnet. |
| `--wasm PATH` | Deploy a specific WASM file (e.g. one built by `stellar contract build --optimize`, which writes to `target/wasm32v1-none/release/`). |

The script reports the contract ID as soon as the deploy succeeds, and writes
`--contract-id-out` *before* initializing, so a failed `initialize` still leaves
you the ID of the instance that is now live.

## Deploy from CI

Run the **Deploy to Testnet** workflow (`Actions → Deploy to Testnet → Run
workflow`).

| Input | Meaning |
|---|---|
| `admin_address` | If set, the contract is initialized with it. Leave empty to deploy uninitialized. |
| `run_smoke_test` | Default on. Runs the smoke test against the newly deployed contract. |

The job re-runs the same gates CI applies (`fmt`, `clippy -D warnings`,
`cargo test`), builds the release WASM, installs a pinned `stellar` CLI, calls
the same `scripts/deploy_contract.sh` you would run locally, then smoke tests the
deployment. The contract ID and its explorer link land in the job summary, which
is written even when the smoke test fails — the deployment already happened, so
the ID must never be lost.

Each run creates a new contract ID. There is no "redeploy" that supersedes a
previous instance.

### Required secret

| Name | Where | What it is |
|---|---|---|
| `TESTNET_DEPLOYER_SECRET` | Environment `testnet` (recommended) or repository secret | A funded Testnet secret key (`S...`). It pays for the deployment and, when the smoke test runs, for that too. |

Using the `testnet` **environment** additionally lets you require reviewer
approval under *Settings → Environments*, which is the sensible gate for an
irreversible action.

## Smoke test

`backend/tests/smoke_testnet.py` is the check that the deployment works. It is
not collected by pytest — it needs the network, a deployed contract, and (for
writes) a funded account.

```bash
cd backend

# Interface and read checks. No key, no fees, safe any time.
CONTRACT_ID=C... uv run python -m tests.smoke_testnet --read-only

# Full round trip: anchors, proves inclusion, renews both entry kinds.
SMOKE_TEST_SIGNER_SECRET=S... uv run python -m tests.smoke_testnet
```

It runs the real client code from `app.services.soroban` against the deployment,
so a pass means the paths the backend actually uses work — not that a mock does:

1. **RPC reachable.** Otherwise every later failure is uninformative.
2. **Interface present.** Simulates `get_total_anchored`, `get_total_batches`,
   and `verify_inclusion` to confirm the deployed contract exposes them.
3. **Anchor round trip.** Anchors a fresh hash, reads it back, and checks the
   stored anomaly score and model version. Also confirms an unknown hash returns
   `None` rather than a stale record.
4. **Batch inclusion.** Builds a 3-leaf tree with `app.services.merkle`, anchors
   the root, and checks that the contract accepts the valid proof and rejects the
   same proof at a different index.
5. **Renewal.** Calls `extend_ttl` and `extend_root_ttl` for the entries it just
   wrote. Both are no-ops on-chain (the entries are nowhere near their renewal
   margin) but still submit a signed transaction, which is the seam that would
   otherwise only break in production.
6. **Counters advanced.** Confirms the writes landed.

Exit codes: `0` all checks passed, `1` at least one failed, `2` misconfigured
(no contract ID, or a write run with no funded signer).

The signer is read from `SMOKE_TEST_SIGNER_SECRET`, falling back to
`DEPLOYER_SECRET` and then `TTL_RENEWAL_SIGNER_SECRET`, so an environment already
set up for a manual deploy or the renewal job needs nothing extra.

### Reading a failure

| Output | Meaning |
|---|---|
| `function not present in the deployed contract — redeploy` | The instance is older than this source. It predates the named function, so anchor/renew/batch calls that use it will fail at runtime. Redeploy. |
| All three interface probes fail with `Error(Storage, MissingValue)` | Nothing is deployed at that contract ID. |
| `Soroban RPC reachable` fails | Network or `SOROBAN_RPC_URL` problem, not a contract problem. |
| `verify_inclusion rejects a wrong index` fails | Serious: the contract accepted a proof for a leaf position that should not verify. Investigate before trusting any batch. |

## Releases

Pushing a `v*` tag publishes a GitHub release containing the built WASM and its
SHA-256:

```bash
git tag -a v0.2.0 -m "GeoGuard Ledger v0.2.0"
git push origin v0.2.0
```

The `Release` workflow first checks that the tag matches the version in
`contracts/geoguard-ledger/Cargo.toml`, `backend/pyproject.toml`, and
`frontend/package.json`, then tests, builds, and attaches
`geoguard_ledger.wasm` plus `geoguard_ledger.wasm.sha256`. A tag that disagrees
with the manifests fails the run rather than publishing an artifact nobody can map
back to a version.

Verify a download with:

```bash
sha256sum -c geoguard_ledger.wasm.sha256
```

## The contract the local stack uses

`docker-compose.yml` pins a `CONTRACT_ID` for the backend container. That value
is **an older deployment than this source** — it predates batch anchoring, so
batch verification and TTL renewal against it fail. To exercise those flows
locally, deploy a current contract and update the ID:

```bash
DEPLOYER_SECRET=S... ./scripts/deploy_contract.sh --admin G... --contract-id-out /tmp/cid
CONTRACT_ID=$(cat /tmp/cid)
cd backend && CONTRACT_ID=$CONTRACT_ID uv run python -m tests.smoke_testnet --read-only
```

Then update `CONTRACT_ID` in `docker-compose.yml` (or `backend/.env`) and restart
the backend.

## Secrets

| Name | Used by | Can it harm anything? |
|---|---|---|
| `DEPLOYER_SECRET` | `scripts/deploy_contract.sh`, dev smoke scripts | Pays fees. A deployment it makes is permanent, so treat the key as privileged. |
| `TESTNET_DEPLOYER_SECRET` | `deploy-testnet.yml` | Same as above, in CI. |
| `SMOKE_TEST_SIGNER_SECRET` | `tests/smoke_testnet.py` | Anchors throwaway hashes and renews entries. Cannot alter or delete an existing record. |
| `TTL_RENEWAL_SIGNER_SECRET` | `app/jobs/renew_ttl.py` | The operational "rent payer". `extend_ttl` and `extend_root_ttl` are permissionless and can only push an expiry *out*, so this key cannot forge, alter, or delete a record — it only spends fees. |

No researcher's key ever reaches the backend: anchoring is signed client-side in
the wallet. Never commit any of these; if one lands in git history, rotate it
on-chain.
