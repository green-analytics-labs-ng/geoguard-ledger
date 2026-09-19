// `vitest/config` re-exports Vite's `defineConfig` with the `test` field typed.
// Vitest and the app share a single Vite install, so the plugin types line up.
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
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
    setupFiles: [],
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
