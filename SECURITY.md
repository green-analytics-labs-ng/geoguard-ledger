# Security Policy

GeoGuard Ledger anchors research integrity proofs on Stellar. A flaw here can
mean a dataset whose integrity can be misrepresented, a key that leaks, or a
signed transaction that does something its signer did not intend — so reports
are welcome and are read by a human.

## Reporting a vulnerability

**Please do not open a public issue for a security problem.**

Two private channels are watched:

1. **GitHub private vulnerability reporting** — the *Report a vulnerability*
   button on the
   [Security tab](https://github.com/green-analytics-labs-ng/geoguard-ledger/security/advisories/new).
   This is preferred: it keeps the whole discussion, the fix, and the advisory
   in one place, and it can issue a CVE.
2. **Email** — `security@greenanalyticslabs.org`. Use this if you cannot use
   GitHub, or if the report contains something you would rather not attach to a
   GitHub account.

Include what you can of:

- the affected component — backend API, Soroban contract, or frontend;
- the commit, tag, or deployed contract ID you tested;
- the request, input file, or transaction that triggers it;
- what an attacker gains, and what they would need to already have;
- any proof of concept, and whether you have shared it elsewhere.

You do not need a working exploit or a polished write-up. A plausible attack on
the anchoring path is worth a report on its own.

## What to expect

| Stage | Target |
|-------|--------|
| Acknowledgement of your report | 3 business days |
| Initial assessment (severity, affected versions) | 10 business days |
| Fix or documented mitigation | 90 days, sooner for anything reachable without a key |
| Credit in the advisory | Included unless you ask otherwise |

If a report is taking longer than these targets, we will say so rather than go
quiet. We will tell you if we conclude something is not a vulnerability, and
why.

## Scope

In scope, roughly in order of how much a finding matters:

- **The Soroban contract** (`contracts/geoguard-ledger`) — anything that lets an
  anchor be forged, replaced, or made to prove something it does not.
  `docs/contract_security.md` states what an anchor is and is not evidence for;
  a flaw that breaks one of those claims is in scope.
- **The backend** (`backend`) — authentication and the API key check, rate
  limiting, request handling, canonicalization and hashing, and the Transaction
  Builder path.
- **The frontend** (`frontend`) — anything that makes a user sign something they
  did not intend, or that displays a verification result the data does not
  support.

Out of scope:

- Findings that require a compromised browser extension, a compromised
  developer machine, or physical access;
- Denial of service through volume alone, unless it is cheap and
  unauthenticated and the rate limits do not blunt it;
- Reports from automated scanners with no demonstrated impact;
- The known limitation that an anchor proves *existence and integrity*, not
  authorship — see `docs/contract_security.md`.

## Known advisories

Not everything the dependency scanners report can be closed by upgrading, and
pretending otherwise just leaves a permanently red check. The production
dependency audit (`npm run audit:prod`, run in CI) therefore fails on anything
*new* while naming what is accepted and why. The current list lives in
`frontend/scripts/audit-production.mjs`, and the notable one is:

- **`toml` (GHSA-82x6-q7mm-w9cf, GHSA-v5mp-jgw5-2x6j)** — high severity,
  transitive through `@stellar/stellar-sdk`, reachable only from that SDK's
  `StellarToml` resolver, which this application never calls. The fix is
  `@stellar/stellar-sdk@17`, a major upgrade tracked separately.

If you believe one of these is reachable in a way the note does not account for,
that is exactly the kind of report this policy wants.

## Supported versions

The project is pre-1.0. Fixes land on `main` and are released as a new tag; only
the latest release is supported. A deployed contract is immutable and is never
"patched" — a contract fix means a new deployment, and the old contract ID stays
valid until its TTL entry expires. If your report concerns a deployed contract,
say which contract ID, because that is the version users actually interact with.

## Safe harbour

We will not pursue or support legal action against researchers who report in
good faith under this policy: test against your own accounts and datasets, do
not access or alter anyone else's data, and give us a reasonable window to fix
the issue before publishing. Act in good faith and you have our thanks.
