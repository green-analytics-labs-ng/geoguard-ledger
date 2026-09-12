# Contributing to GeoGuard Ledger

Thank you for your interest in contributing! GeoGuard Ledger is an open-source research integrity system for Green Analytics Labs, and we welcome contributions from researchers, developers, and data scientists.

## Code of Conduct

This project adheres to a [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## How to Contribute

### 1. Fork & Clone

```bash
git clone https://github.com/YOUR_USERNAME/geoguard-ledger.git
cd geoguard-ledger
```

### 2. Pick an Issue

- Browse [open issues](https://github.com/green-analytics-labs/geoguard-ledger/issues)
- Look for `good-first-issue` or `help-wanted` labels
- For larger features, open a [Discussion](https://github.com/green-analytics-labs/geoguard-ledger/discussions) first

### 3. Create a Branch

```bash
git checkout -b feat/your-feature-name
# or
git checkout -b fix/issue-number
```

### 4. Follow Code Conventions

| Language | Formatter | Linter | Type Checker | Test Runner |
|----------|-----------|--------|--------------|-------------|
| Rust (Soroban) | `cargo fmt` | `cargo clippy` | `cargo check` | `cargo test` |
| Python | `ruff format` | `ruff check` | `mypy` | `pytest` |
| TypeScript | Prettier | ESLint | `tsc --noEmit` | Vitest |

### 5. Write Tests

- New features must include tests
- Bug fixes should include a regression test
- Aim for meaningful coverage, not just line-counting

### 6. Update Documentation

- If you add an endpoint, update `docs/api_reference.md`
- If you change a contract function, update `contracts/README.md`
- If you add a new component, add a brief JSDoc description
- If you change how anything is deployed or released, update `docs/deployment.md`

### 7. Deploying a Contract Change

Contract changes only take effect once they are deployed, and a deployment is
permanent, so a deployed contract can lag this source indefinitely. Before you
trust a deployment — and after any contract change that needs one — verify it
against the network:

```bash
cd backend && CONTRACT_ID=C... python -m tests.smoke_testnet --read-only
```

That check needs no key and spends no fees. The full round trip (which anchors,
proves inclusion, and renews) is `python -m tests.smoke_testnet`. See
[docs/deployment.md](docs/deployment.md).

### 8. Open a Pull Request

- Use the PR template
- Link the related issue
- Include screenshots for UI changes
- Ensure CI passes (lint, test, build)

## Commit Conventions

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(contract): add anchor_hash function
fix(backend): handle CSV with BOM characters
docs: update API reference for verify endpoint
test(frontend): add CsvDropzone unit tests
chore(ci): add Soroban contract test workflow
```

## Development Setup

```bash
# Prerequisites: Docker, Rust, Python 3.11+, Node 18+
./scripts/setup_dev.sh
```

This installs all dependencies, starts PostgreSQL via Docker, runs migrations, deploys a local Soroban instance, and starts the dev servers.

## Communication

- **GitHub Issues:** Bug reports, feature requests, RFCs
- **GitHub Discussions:** Q&A, ideas, community
- **Weekly Community Call:** 30-min sync for active contributors (schedule TBD)

## License

By contributing, you agree that your contributions will be licensed under the [Apache 2.0 License](LICENSE).
