import axios from "axios";

import { getApiKey } from "./apiKey";

// Methods that change state on the server, and so need the API key when the
// backend has `API_KEYS` configured. GET/HEAD/OPTIONS stay unauthenticated:
// public reads and permissionless verification must work without a key.
const WRITE_METHODS = new Set(["post", "put", "patch", "delete"]);

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api/v1",
  headers: {
    "Content-Type": "application/json",
  },
});

client.interceptors.request.use((config) => {
  const apiKey = getApiKey();
  const method = (config.method ?? "get").toLowerCase();
  if (apiKey && WRITE_METHODS.has(method)) {
    config.headers.set("X-API-Key", apiKey);
  }
  return config;
});

export default client;
