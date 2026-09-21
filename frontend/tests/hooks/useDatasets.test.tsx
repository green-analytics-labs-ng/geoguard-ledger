import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";

const api = vi.hoisted(() => ({
  listDatasets: vi.fn(),
  getDataset: vi.fn(),
}));

vi.mock("../../src/api/datasets", () => api);

import { useDatasets } from "../../src/hooks/useDatasets";

function dataset(id: string) {
  return {
    dataset_id: id,
    dataset_hash: "a".repeat(64),
    status: "anchored" as const,
    anomaly_score: 0.1,
    created_at: "2026-07-05T12:00:00Z",
  };
}

describe("useDatasets", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listDatasets.mockResolvedValue({ datasets: [], total: 0 });
  });

  it("starts in a loading state", async () => {
    const { result } = renderHook(() => useDatasets());

    expect(result.current.loading).toBe(true);
    expect(result.current.datasets).toEqual([]);

    // Let the mount-time fetch settle so it does not update state after the test.
    await waitFor(() => expect(result.current.loading).toBe(false));
  });

  it("loads datasets on mount", async () => {
    api.listDatasets.mockResolvedValue({ datasets: [dataset("1"), dataset("2")], total: 2 });
    const { result } = renderHook(() => useDatasets());

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.datasets).toHaveLength(2);
    expect(result.current.error).toBeNull();
  });

  it("exposes the error message when the request fails", async () => {
    api.listDatasets.mockRejectedValue(new Error("Network down"));
    const { result } = renderHook(() => useDatasets());

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe("Network down");
    expect(result.current.datasets).toEqual([]);
  });

  it("falls back to a generic message for non-Error failures", async () => {
    api.listDatasets.mockRejectedValue("boom");
    const { result } = renderHook(() => useDatasets());

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe("Failed to fetch datasets");
  });

  it("refreshes the list on demand", async () => {
    const { result } = renderHook(() => useDatasets());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.refresh();
    });

    expect(api.listDatasets).toHaveBeenCalledTimes(2);
  });

  it("passes an abort signal to the list request", async () => {
    renderHook(() => useDatasets());

    await waitFor(() => expect(api.listDatasets).toHaveBeenCalled());
    expect(api.listDatasets).toHaveBeenCalledWith(expect.any(AbortSignal));
  });

  it("aborts the in-flight request on unmount", async () => {
    let signal: AbortSignal | undefined;
    api.listDatasets.mockImplementation((passed?: AbortSignal) => {
      signal = passed;
      // Never settles, so the request is still open when the page goes away.
      return new Promise(() => undefined);
    });

    const { unmount } = renderHook(() => useDatasets());
    await waitFor(() => expect(signal).toBeDefined());
    expect(signal?.aborted).toBe(false);

    unmount();

    expect(signal?.aborted).toBe(true);
  });

  it("cancels a superseded refresh instead of racing it", async () => {
    const signals: AbortSignal[] = [];
    api.listDatasets.mockImplementation((passed?: AbortSignal) => {
      if (passed) signals.push(passed);
      if (signals.length === 1) return new Promise(() => undefined);
      return Promise.resolve({ datasets: [dataset("7")], total: 1 });
    });

    const { result } = renderHook(() => useDatasets());
    await act(async () => {
      await result.current.refresh();
    });

    expect(signals).toHaveLength(2);
    // The abandoned first request can no longer resolve into state, and the
    // hook is not left spinning on it.
    expect(signals[0].aborted).toBe(true);
    expect(result.current.loading).toBe(false);
    expect(result.current.datasets).toEqual([dataset("7")]);
  });

  it("returns a dataset by id", async () => {
    api.getDataset.mockResolvedValue(dataset("42"));
    const { result } = renderHook(() => useDatasets());
    await waitFor(() => expect(result.current.loading).toBe(false));

    let fetched: unknown = null;
    await act(async () => {
      fetched = await result.current.getDataset("42");
    });

    expect(api.getDataset).toHaveBeenCalledWith("42");
    expect(fetched).toEqual({ status: "found", dataset: dataset("42") });
  });

  it("reports a 404 as not found", async () => {
    api.getDataset.mockRejectedValue({ response: { status: 404, data: { detail: "No such dataset" } } });
    const { result } = renderHook(() => useDatasets());
    await waitFor(() => expect(result.current.loading).toBe(false));

    let fetched: unknown = "unset";
    await act(async () => {
      fetched = await result.current.getDataset("missing");
    });

    expect(fetched).toEqual({ status: "not-found" });
  });

  it("reports a network failure as an error, not as a missing dataset", async () => {
    // No response at all — a timeout or a dropped connection. Saying "not found"
    // here would be telling the researcher their data is gone.
    api.getDataset.mockRejectedValue(new Error("Network Error"));
    const { result } = renderHook(() => useDatasets());
    await waitFor(() => expect(result.current.loading).toBe(false));

    let fetched: unknown = "unset";
    await act(async () => {
      fetched = await result.current.getDataset("42");
    });

    expect(fetched).toEqual({ status: "error", message: "Network Error" });
  });
});
