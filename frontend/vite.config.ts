// `vitest/config` re-exports Vite's `defineConfig` with the `test` field typed.
// Vitest and the app share a single Vite install, so the plugin types line up.
import { defineConfig } from "vitest/config";
import type { Plugin } from "vite";
import react from "@vitejs/plugin-react";

/**
 * What the entry chunk is allowed to weigh.
 *
 * The entry is what every first paint downloads; the heavy data views (Stellar
 * SDK, CSV/XML parsing, Merkle proofs) are already chunks of their own, loaded
 * on navigation. This is roughly what the app measures today plus a little
 * headroom, so crossing it means a dependency crept into the entry — lazy-load
 * it or drop it. If the budget genuinely has to move, move it here and say why
 * in the commit rather than deleting the check.
 *
 * Moved from 250_000 to 270_000 with react-router-dom 7, which is where the
 * budget went: the router is part of the shell by definition and cannot be
 * lazy-loaded, and v7 measures 254.04 kB against 238.18 kB on v6 — it now ships
 * the data-router machinery alongside the declarative API this app uses. The
 * alternative was staying on 6.x, which has no patched release for the
 * open-redirect in GHSA-wrjc-x8rr-h8h6. Kept to the same ~6% headroom over the
 * measured size as before, so a dependency that creeps into the entry still
 * trips it.
 */
const MAIN_CHUNK_BUDGET_BYTES = 270_000;

/**
 * UTF-8 byte length, so the budget counts what the browser downloads.
 *
 * Hand-rolled rather than `Buffer.byteLength` because `tsconfig.node.json`
 * compiles this file against the ES2023 lib alone — no Node type definitions
 * are pulled in, and a string's `.length` is UTF-16 code units, which is not
 * the same number for the non-ASCII characters the UI copy contains.
 */
function byteLength(text: string): number {
  let bytes = 0;
  for (let index = 0; index < text.length; index += 1) {
    const codePoint = text.codePointAt(index) ?? 0;
    if (codePoint > 0xffff) index += 1; // a surrogate pair is one code point
    bytes +=
      codePoint < 0x80 ? 1 : codePoint < 0x800 ? 2 : codePoint < 0x10000 ? 3 : 4;
  }
  return bytes;
}

function formatKb(bytes: number): string {
  return `${(bytes / 1000).toFixed(2)} kB`;
}

/**
 * Fail the build when the entry chunk outgrows its budget.
 *
 * Vite reports sizes but never objects to them, so without this a dependency
 * added to the shared shell is noticed only by users on a slow connection.
 *
 * Measured in `writeBundle`, not `generateBundle`: Vite's own import-analysis
 * hook injects the module-preload helper into the entry chunk during
 * `generateBundle`, so a chunk measured before that is smaller than the file a
 * browser downloads — and smaller than the size Vite prints.
 */
function bundleBudget(): Plugin {
  return {
    name: "bundle-budget",
    apply: "build",
    writeBundle(_options, bundle) {
      // A guard clause rather than a filter, so the union narrows to the chunk
      // and `code` is readable.
      for (const output of Object.values(bundle)) {
        if (output.type !== "chunk" || !output.isEntry) continue;

        const bytes = byteLength(output.code);
        if (bytes > MAIN_CHUNK_BUDGET_BYTES) {
          this.error(
            `${output.fileName} is ${formatKb(bytes)}, over the ` +
              `${formatKb(MAIN_CHUNK_BUDGET_BYTES)} entry budget. Lazy-load the new ` +
              "dependency or split the chunk; raising the budget is a deliberate " +
              "decision, not a fix (see MAIN_CHUNK_BUDGET_BYTES in vite.config.ts).",
          );
        }
        this.info(
          `${output.fileName}: ${formatKb(bytes)} of the ` +
            `${formatKb(MAIN_CHUNK_BUDGET_BYTES)} entry budget.`,
        );
      }
    },
  };
}

export default defineConfig({
  plugins: [react(), bundleBudget()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  // https://vitest.dev/config/
  test: {
    globals: true,
    environment: "jsdom",
    // Registers the vitest-axe matchers that the accessibility smoke tests use
    // (see tests/setup.ts).
    setupFiles: ["./tests/setup.ts"],
    coverage: {
      // v8 reads the ranges V8 already collects, which needs no source
      // instrumentation and so leaves the tests the same code the app runs.
      provider: "v8",
      // `text` prints the table that lands in the CI job log; `json-summary`
      // writes the one number per metric that scripts/coverage_delta.py reads
      // back out of the uploaded artifact.
      reporter: ["text", "json-summary"],
      reportsDirectory: "coverage",
      include: ["src/**/*.{ts,tsx}"],
      // The entry point wires the tree up and renders it once, and the type
      // declarations have no runtime code to cover.
      exclude: ["src/main.tsx", "src/types/**", "src/**/*.d.ts"],
    },
  },
});
