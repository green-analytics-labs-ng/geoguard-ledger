import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { AxiosHeaders, type AxiosResponse, type InternalAxiosRequestConfig } from "axios";

import client, { REQUEST_TIMEOUT_MS } from "../../src/api/client";
import { clearApiKey, setApiKey } from "../../src/api/apiKey";

let sentHeaders: AxiosHeaders | null = null;
let sentTimeout: number | undefined;

// A stub adapter stands in for the network so the test can inspect the headers
// the interceptor produced without a server.
const adapter = async (config: InternalAxiosRequestConfig): Promise<AxiosResponse> => {
  sentHeaders = config.headers;
  sentTimeout = config.timeout;
  return {
    data: null,
    status: 200,
    statusText: "OK",
    headers: new AxiosHeaders(),
    config,
  };
};

/** An adapter that fails the way axios does when the request never succeeds. */
function rejectWith(error: unknown) {
  return async (): Promise<AxiosResponse> => {
    throw error;
  };
}

/**
 * A shape axios produces for a failed request, without the real adapter.
 *
 * `isAxiosError` is what `axios.isAxiosError` checks, and `response` is what the
 * interceptor and the components read the backend's `detail` out of.
 */
function axiosFailure(overrides: Record<string, unknown> = {}): Error {
  return Object.assign(new Error("Request failed with status code 400"), {
    isAxiosError: true,
    ...overrides,
  });
}

function sentKey(): unknown {
  return sentHeaders?.get("X-API-Key");
}

beforeEach(() => {
  sentHeaders = null;
  sentTimeout = undefined;
  clearApiKey();
});

afterEach(() => clearApiKey());

describe("API client key header", () => {
  it("attaches the stored key to write requests", async () => {
    setApiKey("secret-key");

    await client.post("/datasets", {}, { adapter });

    expect(sentKey()).toBe("secret-key");
  });

  it("does not attach the key to reads", async () => {
    setApiKey("secret-key");

    await client.get("/datasets", { adapter });

    expect(sentKey()).toBeFalsy();
  });

  it("sends no header when no key is configured", async () => {
    await client.post("/datasets", {}, { adapter });

    expect(sentKey()).toBeFalsy();
  });

  it("saves a trimmed key", async () => {
    setApiKey("  spaced-key  ");

    await client.post("/batches", {}, { adapter });

    expect(sentKey()).toBe("spaced-key");
  });

  it("does not attach the key to the public verification endpoint", async () => {
    setApiKey("secret-key");

    await client.post("/verify", null, { adapter });

    expect(sentKey()).toBeFalsy();
  });

  it("attaches the key to an anchoring subpath", async () => {
    setApiKey("secret-key");

    await client.post("/datasets/abc/anchor", {}, { adapter });

    expect(sentKey()).toBe("secret-key");
  });

  it("does not attach the key to a lookalike path", async () => {
    setApiKey("secret-key");

    await client.post("/datasets-archive", {}, { adapter });

    expect(sentKey()).toBeFalsy();
  });
});

describe("API client timeout", () => {
  it("applies a deadline to every request", async () => {
    await client.get("/datasets", { adapter });

    // Without one, axios waits forever and a hung request is indistinguishable
    // from a slow server.
    expect(sentTimeout).toBe(REQUEST_TIMEOUT_MS);
  });

  it("explains a timeout instead of quoting the configured milliseconds", async () => {
    const timedOut = axiosFailure({ code: "ECONNABORTED", message: "timeout of 30000ms exceeded" });

    // A timeout never reached a server, so there is no `detail` to prefer.
    await expect(client.get("/datasets", { adapter: rejectWith(timedOut) })).rejects.toThrow(
      /timed out/i,
    );
  });
});

describe("API client error mapping", () => {
  it("prefers the backend's detail over axios's status text", async () => {
    const detail =
      "Your Stellar account GABC is not funded on Testnet. Fund it at https://friendbot.stellar.org?addr=GABC";
    const failure = axiosFailure({ response: { status: 400, data: { detail } } });

    await expect(client.post("/datasets", {}, { adapter: rejectWith(failure) })).rejects.toThrow(
      detail,
    );
  });

  it("leaves the response on the error for callers that read it themselves", async () => {
    const failure = axiosFailure({ response: { status: 400, data: { detail: "Fund it first" } } });

    await expect(
      client.post("/datasets", {}, { adapter: rejectWith(failure) }),
    ).rejects.toMatchObject({ response: { status: 400, data: { detail: "Fund it first" } } });
  });

  it("falls back to a generic message when there is nothing to show", async () => {
    // A thrown string is not an Error and carries no response at all.
    await expect(client.get("/datasets", { adapter: rejectWith("boom") })).rejects.toThrow(
      "The request failed. Please try again.",
    );
  });
});
