import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { AxiosHeaders, type AxiosResponse, type InternalAxiosRequestConfig } from "axios";

import client from "../../src/api/client";
import { clearApiKey, setApiKey } from "../../src/api/apiKey";

let sentHeaders: AxiosHeaders | null = null;

// A stub adapter stands in for the network so the test can inspect the headers
// the interceptor produced without a server.
const adapter = async (config: InternalAxiosRequestConfig): Promise<AxiosResponse> => {
  sentHeaders = config.headers;
  return {
    data: null,
    status: 200,
    statusText: "OK",
    headers: new AxiosHeaders(),
    config,
  };
};

function sentKey(): unknown {
  return sentHeaders?.get("X-API-Key");
}

beforeEach(() => {
  sentHeaders = null;
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
});
