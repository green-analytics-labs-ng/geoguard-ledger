import { useState, useEffect, useCallback } from "react";
import { listDatasets, getDataset as apiGetDataset } from "../api/datasets";
import type { DatasetResponse } from "../types";

interface UseDatasetsReturn {
  datasets: DatasetResponse[];
  loading: boolean;
  error: string | null;
  getDataset: (id: string) => Promise<DatasetResponse | null>;
  refresh: () => Promise<void>;
}

export function useDatasets(): UseDatasetsReturn {
  const [datasets, setDatasets] = useState<DatasetResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDatasets = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listDatasets();
      setDatasets(data.datasets);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to fetch datasets";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDatasets();
  }, [fetchDatasets]);

  const getDataset = useCallback(
    async (id: string): Promise<DatasetResponse | null> => {
      try {
        return await apiGetDataset(id);
      } catch {
        return null;
      }
    },
    [],
  );

  return { datasets, loading, error, getDataset, refresh: fetchDatasets };
}
