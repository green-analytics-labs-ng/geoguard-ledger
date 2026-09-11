import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";

const api = vi.hoisted(() => ({
  verifyByHash: vi.fn(),
  verifyByFile: vi.fn(),
  verifyById: vi.fn(),
}));

vi.mock("../../src/api/verify", () => api);

import { useVerify } from "../../src/hooks/useVerify";

const HASH = "a".repeat(64);

const MATCH = {
  match: true,
  on_chain_record: {
    dataset_hash: HASH,
    anomaly_score: 0,
    model_version: "isoforest_v1",
    timestamp: 1751715300,
    submitter: "GABC",
  },
  local_record: null,
};

describe("useVerify", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.verifyByHash.mockResolvedValue(MATCH);
    api.verifyById.mockResolvedValue(MATCH);
    api.verifyByFile.mockResolvedValue({ ...MATCH, re_computed_hash: HASH });
  });

  it("verifies by hash when given a 64-character digest", async () => {
    const { result } = renderHook(() => useVerify());

    await act(async () => {
      await result.current.verify(HASH);
    });

    expect(api.verifyByHash).toHaveBeenCalledWith(HASH);
    expect(api.verifyById).not.toHaveBeenCalled();
    expect(result.current.result?.match).toBe(true);
    expect(result.current.error).toBeNull();
  });

  it("verifies by dataset id for a shorter input", async () => {
    const { result } = renderHook(() => useVerify());

    await act(async () => {
      await result.current.verify("11111111-2222-3333-4444-555555555555");
    });

    expect(api.verifyById).toHaveBeenCalledTimes(1);
    expect(api.verifyByHash).not.toHaveBeenCalled();
  });

  it("verifies by file upload when given a File", async () => {
    const { result } = renderHook(() => useVerify());
    const file = new File(["a,b\n1,2\n"], "data.csv", { type: "text/csv" });

    await act(async () => {
      await result.current.verify(file);
    });

    expect(api.verifyByFile).toHaveBeenCalledWith(file);
    expect(result.current.result?.re_computed_hash).toBe(HASH);
  });

  it("exposes the backend error message on failure", async () => {
    api.verifyByHash.mockRejectedValue(new Error("Soroban RPC unreachable"));
    const { result } = renderHook(() => useVerify());

    await act(async () => {
      await result.current.verify(HASH);
    });

    expect(result.current.error).toBe("Soroban RPC unreachable");
    expect(result.current.result).toBeNull();
  });

  it("falls back to a generic message for non-Error failures", async () => {
    api.verifyByHash.mockRejectedValue("nope");
    const { result } = renderHook(() => useVerify());

    await act(async () => {
      await result.current.verify(HASH);
    });

    expect(result.current.error).toBe("Verification failed");
  });

  it("toggles loading while in flight", async () => {
    let release: (value: unknown) => void = () => undefined;
    api.verifyByHash.mockImplementation(
      () => new Promise((resolve) => { release = resolve; }),
    );
    const { result } = renderHook(() => useVerify());

    act(() => {
      void result.current.verify(HASH);
    });

    await waitFor(() => expect(result.current.loading).toBe(true));

    await act(async () => {
      release(MATCH);
    });

    expect(result.current.loading).toBe(false);
  });

  it("clears the previous result and error", async () => {
    const { result } = renderHook(() => useVerify());

    await act(async () => {
      await result.current.verify(HASH);
    });
    expect(result.current.result).not.toBeNull();

    act(() => {
      result.current.clear();
    });

    expect(result.current.result).toBeNull();
    expect(result.current.error).toBeNull();
  });
});
