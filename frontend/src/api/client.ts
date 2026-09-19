import axios from "axios";

import { getApiKey } from "./apiKey";

// Methods that change state on the server.
const WRITE_METHODS = new Set(["post", "put", "patch", "delete"]);

// The write endpoints the backend protects with `API_KEYS`: uploads and
// anchoring. This is deliberately an allowlist rather than "every write except
// verification", so the shared secret can only ever be sent where it is
// expected — a new public endpoint cannot leak it, and a new protected one
// surfaces as a 401 instead of a silent omission. `POST /verify` is absent on
// purpose: permissionless verification is a feature, so it must stay public and
// must never carry the key.
const AUTHENTICATED_WRITE_PATHS = ["/datasets", "/batches"];

// Segment-aware so `/datasets` matches `/datasets/abc/anchor` but not a
// lookalike such as `/datasets-archive`.
function needsApiKey(method: string, url: string): boolean {
  if (!WRITE_METHODS.has(method)) {
    return false;
  }
  const path = url.split("?")[0];
  return AUTHENTICATED_WRITE_PATHS.some(
    (prefix) => path === prefix || path.startsWith(`${prefix}/`),
  );
}

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api/v1",
  headers: {
    "Content-Type": "application/json",
  },
});

client.interceptors.request.use((config) => {
  const apiKey = getApiKey();
  const method = (config.method ?? "get").toLowerCase();
  if (apiKey && needsApiKey(method, config.url ?? "")) {
    config.headers.set("X-API-Key", apiKey);
  }
  return config;
});

export default client;
