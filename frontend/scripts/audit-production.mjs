#!/usr/bin/env node
/**
 * Audit production dependencies, naming the findings we ship with.
 *
 * `npm audit --omit=dev` is a binary: any finding fails the build. Every finding
 * that used to sit below was closed by a semver-major upgrade this release
 * makes, so the accepted list is now empty and the gate enforces that directly.
 *
 * The list stays rather than being deleted along with its last entry: when an
 * upgrade cannot land, recording its advisory here with the reason it is not
 * reachable is what keeps the gate meaningful — a gate that is always red gets
 * ignored or deleted within a week.
 *
 * Deliberately no count is stated here: entries are added and removed as
 * upgrades land, and a number in this paragraph is one more thing to forget to
 * update. The list below is the count.
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
 * Empty on purpose, and provably so: the four findings this release shipped with
 * — two react-router 6 ones and two reaching `toml` through
 * @stellar/stellar-sdk 16 — are all cleared by the semver-major upgrades it
 * makes, and each was deleted with the upgrade that cleared it. That is the
 * whole lifecycle: an entry exists only while its upgrade is still blocked.
 *
 * `clearedBy` is deliberately a concrete change, not "a future upgrade": when
 * that change lands, this entry is deleted and the gate goes back to enforcing
 * an empty list, which is the state below.
 *
 * @type {Map<string, { id: string, package: string, reason: string, clearedBy: string }>}
 */
const ACCEPTED = new Map();

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

// The empty list above is the normal case now, so say so plainly rather than
// reporting a count of zero.
console.log(
  found.size === 0
    ? "\n✅ No advisories in production dependencies."
    : `\n✅ ${found.size} advisory(ies) in production dependencies, all accepted.`,
);
