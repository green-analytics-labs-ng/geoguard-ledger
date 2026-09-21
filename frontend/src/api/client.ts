import axios from "axios";

import { getApiKey } from "./apiKey";
import { apiErrorMessage } from "../utils/errors";

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

/**
 * Deadline for the calls that answer from a row or two of database.
 *
 * Without one, a request that never answers hangs the UI on a spinner forever:
 * axios waits indefinitely by default, so a dropped connection or a proxy that
 * ate the response looks identical to a slow server.
 */
export const REQUEST_TIMEOUT_MS = 30_000;

/**
 * Deadline for the two endpoints that take a file.
 *
 * They are a different shape of request. The backend canonicalizes, hashes and
 * scores up to `MAX_UPLOAD_SIZE_BYTES` (50 MB) before it answers, which over a
 * slow connection is minutes rather than seconds — the default would cut the
 * analysis off mid-flight and report it as a network failure.
 */
export const UPLOAD_TIMEOUT_MS = 120_000;

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api/v1",
  headers: {
    "Content-Type": "application/json",
  },
  timeout: REQUEST_TIMEOUT_MS,
});

client.interceptors.request.use((config) => {
  const apiKey = getApiKey();
  const method = (config.method ?? "get").toLowerCase();
  if (apiKey && needsApiKey(method, config.url ?? "")) {
    config.headers.set("X-API-Key", apiKey);
  }
  return config;
});

/** The codes axios reports when a request ran out of time. */
const TIMEOUT_CODES = new Set(["ECONNABORTED", "ETIMEDOUT"]);

const TIMEOUT_MESSAGE =
  "The request timed out before the server answered. Check your connection and try again.";

client.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    // A timeout never reached a server, so there is no `detail` to prefer;
    // axios's own "timeout of 30000ms exceeded" is written for a developer.
    const timedOut =
      axios.isAxiosError(error) && error.code !== undefined && TIMEOUT_CODES.has(error.code);

    const message = timedOut
      ? TIMEOUT_MESSAGE
      : apiErrorMessage(error, "The request failed. Please try again.");

    // Rewrite the message on the original error rather than replacing it: the
    // components still read `response.data.detail` and `config` off the same
    // object, while callers that only look at `message` now get the backend's
    // actionable half instead of "Request failed with status code 400".
    if (error instanceof Error) {
      error.message = message;
      return Promise.reject(error);
    }
    return Promise.reject(new Error(message));
  },
);

export default client;
