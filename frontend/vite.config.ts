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
  },
});
