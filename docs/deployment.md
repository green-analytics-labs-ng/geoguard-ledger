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

## Scheduling the TTL renewal job

Anchors are Persistent ledger entries, so they are archived once their TTL
lapses and verification stops answering for whatever they covered. The renewal
job is the rent payer that keeps them alive; run it on a schedule tighter than
`TTL_RENEWAL_WINDOW_DAYS` (30 by default).

Installing the backend installs a console script for it, so a scheduler can call
it by name instead of by module path:

```bash
uv sync                    # creates .venv/bin/geoguard-renew-ttl
uv run geoguard-renew-ttl --dry-run    # list what would be renewed, spends nothing
```

`geoguard-renew-ttl` and `python -m app.jobs.renew_ttl` run the same entry point
and accept the same `--dry-run` and `--limit` flags.

It needs `CONTRACT_ID`, `DATABASE_URL`, `TTL_RENEWAL_ENABLED=true`, and
`TTL_RENEWAL_SIGNER_SECRET` — see [Secrets](#secrets) for what that key can do
(it can only spend fees, never alter a record). Use the venv's absolute path:
the script's shebang points at the venv interpreter, so no activation is needed,
which suits schedulers that start with a minimal environment.

### cron

```cron
# Daily at 03:00. Cron's PATH is minimal, hence absolute paths throughout.
0 3 * * * cd /opt/geoguard/backend && ./.venv/bin/geoguard-renew-ttl >> /var/log/geoguard-ttl.log 2>&1
```

### systemd

```ini
# /etc/systemd/system/geoguard-renew-ttl.service
[Unit]
Description=Renew GeoGuard Ledger Soroban TTLs

[Service]
Type=oneshot
WorkingDirectory=/opt/geoguard/backend
EnvironmentFile=/etc/geoguard/backend.env
ExecStart=/opt/geoguard/backend/.venv/bin/geoguard-renew-ttl
```

```ini
# /etc/systemd/system/geoguard-renew-ttl.timer
[Unit]
Description=Daily GeoGuard Ledger TTL renewal

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
systemctl enable --now geoguard-renew-ttl.timer
```

### Alerting on failure

The exit code is the signal to alert on:

| Code | Meaning |
|---|---|
| `0` | Ran cleanly, including "nothing was due". |
| `1` | At least one renewal failed. The error is recorded on the entry's row, and the next run retries it. |
| `2` | Not configured — the job is disabled or has no signing key. Nothing was renewed, so treat this as urgent: the entries are drifting toward archival. |

Because the job is safe to re-run (a successful renewal moves the deadline out of
the window), a retry is always the first response to a `1`.

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

`docker-compose.yml` pins a `CONTRACT_ID` for the backend container, and
`backend/.env` pins one for local runs. Those values were once an older
deployment that predated batch anchoring — precisely the drift the smoke test
reports — so re-check them whenever the contract source changes.

To deploy a replacement:

```bash
DEPLOYER_SECRET=S... ./scripts/deploy_contract.sh --admin G... --write-env --contract-id-out /tmp/cid
cd backend && CONTRACT_ID=$(cat /tmp/cid) uv run python -m tests.smoke_testnet --read-only
```

`--write-env` updates `backend/.env`; `docker-compose.yml` does not read that
file, so update its `CONTRACT_ID` too and restart the backend.

A deployment is a new, permanent instance. Datasets anchored against the
previous one stay bound to it and still verify, so replacing the ID does not
invalidate them — it only changes which contract the local stack talks to.

Should you update it again, `CONTRACT_ID` changes in both places; the
`--contract-id-out` file the deploy script writes is what CI uses to hand the ID
to the smoke test within a single run.

## Database schema and boot order

The Postgres schema belongs to Alembic, and the backend never creates tables
itself. That ordering matters, because a table created outside a migration has
no recorded revision: Alembic then treats the database as empty, and
`alembic upgrade head` fails on `relation "datasets" already exists`. A database
in that state cannot be migrated at all until it is stamped (see the repair
below).

The backend container therefore migrates **before** it serves, in one command:

```bash
uv run alembic upgrade head && exec uv run uvicorn app.main:app ...
```

A database that is behind fails there, at boot, with Alembic's own diagnostics —
not at the first request, and not by silently acquiring a schema. When several
replicas run, migrations on boot would race each other; run them as a separate
step ahead of the rollout instead of letting each instance do it.

For a one-off or a manual host:

```bash
cd backend
uv run alembic current          # what this database is on
uv run alembic upgrade head     # bring it up to date (a no-op when it is)
uv run alembic check            # does the schema still match the models?
```

`alembic check` is also a CI gate, so a model change with no migration fails the
build rather than reaching a deployment.

### Rolling a migration back

```bash
uv run alembic downgrade -1
```

Check the migration's `downgrade()` before running it: it has to undo whatever
`upgrade()` did, and some of that cannot be undone faithfully. `b3d7c1a9f204`
(which allows a dataset to exist before it is anchored) is the case to watch —
rolling it back restores `submitter_address`'s `NOT NULL`, so it **deletes
analyzed datasets that were never anchored**, since they have no address to
restore. They were never submitted, so nothing on-chain refers to them, but any
draft work on that host is gone.

### Repairing an unstamped database

Recognise it by the missing version table combined with tables that exist:

```sql
SELECT * FROM alembic_version;   -- ERROR: relation does not exist
\dt                              -- datasets, batches
```

`alembic stamp` writes the version table without running any DDL, so the fix is
to record the revision the schema already is, then upgrade from there:

```bash
# Which revision? Compare against a database migrated from scratch:
#   createdb geoguard_fresh
#   DATABASE_URL=...geoguard_fresh uv run alembic upgrade head
#   pg_dump -s both and diff — column *order* is the giveaway: create_all
#   leaves columns in model-declaration order, migrations append them.
uv run alembic stamp 849a9e96fe36
uv run alembic upgrade head
uv run alembic check             # clean here means you stamped the right one
```

A clean `alembic check` is the proof the repair worked, and it is cheap to run
before committing to anything: it exits non-zero on any drift the models and the
database disagree about.

## Secrets

| Name | Used by | Can it harm anything? |
|---|---|---|
| `DEPLOYER_SECRET` | `scripts/deploy_contract.sh`, dev smoke scripts | Pays fees. A deployment it makes is permanent, so treat the key as privileged. |
| `TESTNET_DEPLOYER_SECRET` | `deploy-testnet.yml` | Same as above, in CI. |
| `SMOKE_TEST_SIGNER_SECRET` | `tests/smoke_testnet.py` | Anchors throwaway hashes and renews entries. Cannot alter or delete an existing record. |
| `TTL_RENEWAL_SIGNER_SECRET` | `geoguard-renew-ttl` (or `python -m app.jobs.renew_ttl`) | The operational "rent payer". `extend_ttl` and `extend_root_ttl` are permissionless and can only push an expiry *out*, so this key cannot forge, alter, or delete a record — it only spends fees. |

No researcher's key ever reaches the backend: anchoring is signed client-side in
the wallet. Never commit any of these; if one lands in git history, rotate it
on-chain.
