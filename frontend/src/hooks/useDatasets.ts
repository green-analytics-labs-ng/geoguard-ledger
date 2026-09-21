import { useState, useEffect, useCallback, useRef } from "react";
import { listDatasets, getDataset as apiGetDataset } from "../api/datasets";
import { apiErrorStatus } from "../utils/errors";
import type { DatasetResponse } from "../types";

/**
 * The outcome of looking one dataset up by id.
 *
 * `not-found` and `error` are deliberately different answers: a 404 is the
 * server saying the dataset does not exist, while a timeout or a 500 is a
 * failure to ask. Collapsing both into `null` meant a researcher with a flaky
 * connection was told their dataset had vanished.
 */
export type DatasetLookup =
  | { status: "found"; dataset: DatasetResponse }
  | { status: "not-found" }
  | { status: "error"; message: string };

interface UseDatasetsReturn {
  datasets: DatasetResponse[];
  loading: boolean;
  error: string | null;
  getDataset: (id: string) => Promise<DatasetLookup>;
  refresh: () => Promise<void>;
}

export function useDatasets(): UseDatasetsReturn {
  const [datasets, setDatasets] = useState<DatasetResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // The request in flight, if any. A refresh replaces it and unmounting aborts
  // it, so a slow answer can never land on a page that has moved on.
  const requestRef = useRef<AbortController | null>(null);

  const fetchDatasets = useCallback(async () => {
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;

    setLoading(true);
    setError(null);
    try {
      const data = await listDatasets(controller.signal);
      setDatasets(data.datasets);
    } catch (err) {
      // An abort is the caller saying "never mind", not a failure to report.
      if (controller.signal.aborted) return;
      const message = err instanceof Error ? err.message : "Failed to fetch datasets";
      setError(message);
    } finally {
      // Guarded: an aborted request must not clear the spinner of the request
      // that replaced it.
      if (!controller.signal.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchDatasets();
    return () => requestRef.current?.abort();
  }, [fetchDatasets]);

  const getDataset = useCallback(async (id: string): Promise<DatasetLookup> => {
    try {
      return { status: "found", dataset: await apiGetDataset(id) };
    } catch (err) {
      if (apiErrorStatus(err) === 404) {
        return { status: "not-found" };
      }
      const message = err instanceof Error ? err.message : "Failed to load dataset";
      return { status: "error", message };
    }
  }, []);

  return { datasets, loading, error, getDataset, refresh: fetchDatasets };
}
