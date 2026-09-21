import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";

const api = vi.hoisted(() => ({ getDataset: vi.fn() }));

vi.mock("../../src/api/datasets", () => api);

import {
  usePendingAnchor,
  INITIAL_POLL_DELAY_MS,
  MAX_POLL_DELAY_MS,
} from "../../src/hooks/usePendingAnchor";
import type { DatasetResponse } from "../../src/types";

function dataset(status: DatasetResponse["status"]): DatasetResponse {
  return {
    dataset_id: "ds-1",
    dataset_hash: "a".repeat(64),
    status,
    anomaly_score: 0.1,
    created_at: "2026-07-05T12:00:00Z",
  };
}

/** Let the mount-time fetch settle without advancing the clock. */
async function flush(): Promise<void> {
  await act(async () => undefined);
}

/** Advance the clock and let whatever it triggered settle. */
async function advance(ms: number): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

describe("usePendingAnchor", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("re-checks a pending dataset until it is anchored", async () => {
    api.getDataset
      .mockResolvedValueOnce(dataset("pending"))
      .mockResolvedValueOnce(dataset("pending"))
      .mockResolvedValueOnce(dataset("anchored"));

    const { result } = renderHook(() => usePendingAnchor("ds-1"));
    await flush();

    expect(api.getDataset).toHaveBeenCalledTimes(1);
    expect(result.current.dataset?.status).toBe("pending");
    expect(result.current.polling).toBe(true);

    await advance(INITIAL_POLL_DELAY_MS);
    expect(api.getDataset).toHaveBeenCalledTimes(2);

    // The second wait is twice the first: this is the backoff, not a fixed
    // interval.
    await advance(INITIAL_POLL_DELAY_MS);
    expect(api.getDataset).toHaveBeenCalledTimes(2);

    await advance(INITIAL_POLL_DELAY_MS);
    expect(api.getDataset).toHaveBeenCalledTimes(3);
    expect(result.current.dataset?.status).toBe("anchored");
    expect(result.current.polling).toBe(false);
    expect(result.current.loading).toBe(false);
  });

  it("stops polling once the dataset is anchored", async () => {
    api.getDataset
      .mockResolvedValueOnce(dataset("pending"))
      .mockResolvedValueOnce(dataset("anchored"));

    renderHook(() => usePendingAnchor("ds-1"));
    await flush();
    await advance(INITIAL_POLL_DELAY_MS);
    expect(api.getDataset).toHaveBeenCalledTimes(2);

    // A terminal status schedules nothing, however long the page stays open.
    await advance(MAX_POLL_DELAY_MS * 4);
    expect(api.getDataset).toHaveBeenCalledTimes(2);
  });

  it("stops polling when the anchor fails", async () => {
    api.getDataset
      .mockResolvedValueOnce(dataset("pending"))
      .mockResolvedValueOnce(dataset("failed"));

    const { result } = renderHook(() => usePendingAnchor("ds-1"));
    await flush();
    await advance(INITIAL_POLL_DELAY_MS);

    expect(result.current.dataset?.status).toBe("failed");
    expect(result.current.polling).toBe(false);

    await advance(MAX_POLL_DELAY_MS * 4);
    expect(api.getDataset).toHaveBeenCalledTimes(2);
  });

  it("stops polling on unmount", async () => {
    api.getDataset.mockResolvedValue(dataset("pending"));

    const { unmount } = renderHook(() => usePendingAnchor("ds-1"));
    await flush();
    await advance(INITIAL_POLL_DELAY_MS);
    expect(api.getDataset).toHaveBeenCalledTimes(2);

    unmount();

    await advance(MAX_POLL_DELAY_MS * 4);
    expect(api.getDataset).toHaveBeenCalledTimes(2);
  });

  it("stops polling and reports the failure when a check errors", async () => {
    api.getDataset
      .mockResolvedValueOnce(dataset("pending"))
      .mockRejectedValueOnce(new Error("Soroban RPC unreachable"));

    const { result } = renderHook(() => usePendingAnchor("ds-1"));
    await flush();
    await advance(INITIAL_POLL_DELAY_MS);

    expect(result.current.error).toBe("Soroban RPC unreachable");
    expect(result.current.polling).toBe(false);
    expect(result.current.loading).toBe(false);

    // A failing endpoint is not retried on a timer: that would turn a broken
    // backend into a request storm.
    await advance(MAX_POLL_DELAY_MS * 4);
    expect(api.getDataset).toHaveBeenCalledTimes(2);
  });

  it("restarts the backoff when refreshed by hand", async () => {
    api.getDataset.mockResolvedValue(dataset("pending"));

    const { result } = renderHook(() => usePendingAnchor("ds-1"));
    await flush();
    expect(api.getDataset).toHaveBeenCalledTimes(1);

    await act(async () => {
      result.current.refresh();
    });

    // An explicit refresh fetches immediately rather than waiting out the
    // remainder of the current delay.
    expect(api.getDataset).toHaveBeenCalledTimes(2);
  });

  it("reports an Error and a fallback message consistently", async () => {
    api.getDataset.mockRejectedValueOnce("not an Error");

    const { result } = renderHook(() => usePendingAnchor("ds-1"));
    await flush();

    expect(result.current.error).toBe("Failed to load dataset");
    expect(result.current.loading).toBe(false);
  });
});
