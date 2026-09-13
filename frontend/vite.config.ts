import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// Vitest reads this block out of the Vite config. It is declared locally
// because Vitest 2 bundles its own Vite 5, so `vitest/config` and the
// `vitest/config` type reference resolve `vite` to that nested copy rather
// than the Vite 6 this project builds with — pulling either in makes the
// plugin types mutually incompatible.
interface VitestOptions {
  globals: boolean;
  environment: string;
  setupFiles: string[];
}

// Kept in a `const` rather than inline: `vite`'s `defineConfig` has no `test`
// field, and passing an object literal directly would be rejected as having
// excess properties.
const config = {
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
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
  } satisfies VitestOptions,
};

export default defineConfig(config);
