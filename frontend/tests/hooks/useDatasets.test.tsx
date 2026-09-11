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

  it("returns a dataset by id", async () => {
    api.getDataset.mockResolvedValue(dataset("42"));
    const { result } = renderHook(() => useDatasets());
    await waitFor(() => expect(result.current.loading).toBe(false));

    let fetched: unknown = null;
    await act(async () => {
      fetched = await result.current.getDataset("42");
    });

    expect(api.getDataset).toHaveBeenCalledWith("42");
    expect(fetched).toEqual(dataset("42"));
  });

  it("returns null from getDataset when the request fails", async () => {
    api.getDataset.mockRejectedValue(new Error("404"));
    const { result } = renderHook(() => useDatasets());
    await waitFor(() => expect(result.current.loading).toBe(false));

    let fetched: unknown = "unset";
    await act(async () => {
      fetched = await result.current.getDataset("missing");
    });

    expect(fetched).toBeNull();
  });
});
