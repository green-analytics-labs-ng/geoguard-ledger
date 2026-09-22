#!/usr/bin/env node
/**
 * Audit production dependencies, naming the findings we ship with.
 *
 * `npm audit --omit=dev` is a binary: any finding fails the build. Two findings
 * here cannot be closed without a semver-major upgrade that this release is not
 * making, so the plain command leaves CI red on every run — and a gate that is
 * always red gets ignored or deleted within a week.
 *
 * This runs the same audit and subtracts the advisories listed below, so a new
 * advisory still fails the build while the accepted ones are explicit: each one
 * records why it is not reachable here and what change clears it. An accepted
 * risk with no owner is just an ignored one.
 *
 * Usage:
 *   npm run audit:prod
 *
 * Exits 0 when every finding is accepted, 1 otherwise (including when npm
 * cannot be reached — an audit that did not run is not a pass).
 */

import { execFileSync } from "node:child_process";

/**
 * Advisories this release ships with, keyed by GitHub advisory id.
 *
 * `clearedBy` is deliberately a concrete change, not "a future upgrade": when
 * that change lands, this entry is deleted and the gate goes back to enforcing
 * an empty list.
 */
const ACCEPTED = new Map(
  [
    {
      id: "GHSA-82x6-q7mm-w9cf",
      package: "toml",
      reason:
        "`toml` only arrives as a transitive dependency of @stellar/stellar-sdk, " +
        "which uses it in one place: the StellarToml resolver that fetches a " +
        "domain's /.well-known/stellar.toml. Nothing in this frontend calls that " +
        "resolver, so no attacker-supplied TOML reaches the parser. npm's fix is " +
        "@stellar/stellar-sdk 17, a major upgrade with its own Soroban RPC changes.",
      clearedBy: "the @stellar/stellar-sdk 17 upgrade",
    },
    {
      id: "GHSA-v5mp-jgw5-2x6j",
      package: "toml",
      reason:
        "Prototype pollution in the same toml dependency, and unreachable for the " +
        "same reason: this frontend never parses a TOML document.",
      clearedBy: "the @stellar/stellar-sdk 17 upgrade",
    },
  ].map((advisory) => [advisory.id, advisory]),
);

const npm = process.platform === "win32" ? "npm.cmd" : "npm";

/** `npm audit --json` output, whether or not npm considered the run a failure. */
function runAudit() {
  try {
    return execFileSync(npm, ["audit", "--omit=dev", "--json"], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
      maxBuffer: 64 * 1024 * 1024,
    });
  } catch (error) {
    // npm exits non-zero as soon as it finds anything, which is the expected
    // case here. The report is still on stdout, so only a run with no output at
    // all is a real failure.
    if (typeof error.stdout === "string" && error.stdout.trim() !== "") {
      return error.stdout;
    }
    throw error;
  }
}

/**
 * The advisories in a report, deduplicated by id.
 *
 * A `via` entry is either the name of a package (a dependency is vulnerable
 * because something it needs is) or an advisory object. Only the objects are
 * advisories; the names are how npm walks the tree to the one that is.
 */
function advisoriesIn(report) {
  const found = new Map();
  for (const vulnerability of Object.values(report.vulnerabilities ?? {})) {
    for (const via of vulnerability.via) {
      if (typeof via === "string") continue;
      // Fall back to npm's numeric id so an advisory without a URL still fails
      // the gate instead of slipping through unmatched.
      const id = via.url?.split("/").pop() ?? (via.source ? `advisory-${via.source}` : null);
      if (id && !found.has(id)) {
        found.set(id, { id, severity: via.severity, package: via.name, title: via.title });
      }
    }
  }
  return found;
}

let report;
try {
  report = JSON.parse(runAudit());
} catch (error) {
  console.error(`Could not read an audit report from npm: ${error.message}`);
  process.exit(1);
}

if (report.error) {
  console.error(
    `The audit did not run: ${report.error.summary ?? report.error.code ?? "unknown error"}`,
  );
  // An audit that could not run must not look like a clean one.
  process.exit(1);
}

const found = advisoriesIn(report);
const unaccepted = [...found.values()].filter((advisory) => !ACCEPTED.has(advisory.id));
const stale = [...ACCEPTED.values()].filter((advisory) => !found.has(advisory.id));

console.log("Production dependency audit\n");
for (const advisory of found.values()) {
  const verdict = ACCEPTED.has(advisory.id) ? "accepted" : "NEW     ";
  console.log(
    `  ${verdict}  ${String(advisory.severity).padEnd(8)} ${String(advisory.package).padEnd(20)} ` +
      `${advisory.id}  ${advisory.title}`,
  );
}

for (const advisory of ACCEPTED.values()) {
  console.log(`\n  ${advisory.id} (${advisory.package})`);
  console.log(`    ${advisory.reason}`);
  console.log(`    Cleared by ${advisory.clearedBy}.`);
}

if (stale.length > 0) {
  // Not a failure: this is the good news case, and the entry just needs a tidy
  // up so the list does not keep growing.
  console.log(
    `\n  Note: ${stale.map((advisory) => advisory.id).join(", ")} ` +
      "is no longer reported — remove it from ACCEPTED.",
  );
}

if (unaccepted.length > 0) {
  console.error(
    `\n❌ ${unaccepted.length} advisory(ies) in production dependencies are not accepted:\n` +
      unaccepted.map((advisory) => `  - ${advisory.id} (${advisory.package})`).join("\n") +
      "\n\nUpgrade the dependency, or add the advisory to ACCEPTED in " +
      "scripts/audit-production.mjs with the reason it is not reachable.\n",
  );
  process.exit(1);
}

console.log(`\n✅ ${found.size} advisory(ies) in production dependencies, all accepted.`);
