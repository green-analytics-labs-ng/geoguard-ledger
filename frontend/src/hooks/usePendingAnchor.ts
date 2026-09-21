import { useCallback, useEffect, useState } from "react";
import { getDataset } from "../api/datasets";
import type { DatasetResponse } from "../types";

/**
 * Statuses that will never change again, so a re-check would only add load.
 *
 * `analyzed` is deliberately absent: it is the state a dataset sits in between
 * upload and anchoring, which is exactly the window a pending anchor is waiting
 * on.
 */
const TERMINAL_STATUSES = new Set<DatasetResponse["status"]>(["anchored", "failed"]);

/**
 * Backoff for the re-checks: every delay is twice the last one, capped.
 *
 * The first check lands a second after anchoring is requested, because that is
 * when the transaction is most likely to have just confirmed; the cap keeps a
 * dataset that never settles (a dropped transaction, a stalled Sourceready)
 * from turning into a request every second for as long as the tab is open.
 */
export const INITIAL_POLL_DELAY_MS = 1_000;
export const MAX_POLL_DELAY_MS = 15_000;

export interface PendingAnchorState {
  dataset: DatasetResponse | null;
  loading: boolean;
  error: string | null;
  /** True while a re-check is scheduled or in flight. */
  polling: boolean;
  /** Re-check now and restart the backoff. */
  refresh: () => void;
}

/**
 * Fetch a dataset, then keep re-checking it while its anchor is unresolved.
 *
 * A dataset is written as `pending` when the signed transaction is submitted,
 * and only becomes `anchored` or `failed` once the backend has seen it on the
 * ledger. Before this, the detail page showed whatever the first response said
 * for the rest of its life: a researcher who anchored a dataset and stayed on
 * the page was told it was still pending until they hit reload.
 *
 * Every path out of the loop is explicit — a terminal status, an error, an
 * unmount, or a superseding fetch — so a page left open cannot accumulate
 * timers.
 */
export function usePendingAnchor(datasetId: string | undefined): PendingAnchorState {
  const [dataset, setDataset] = useState<DatasetResponse | null>(null);
  const [loading, setLoading] = useState(Boolean(datasetId));
  const [error, setError] = useState<string | null>(null);
  const [polling, setPolling] = useState(false);

  // Bumping this re-runs the effect, which is how `refresh` restarts the loop
  // with a fresh backoff sequence.
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    if (!datasetId) return;

    let cancelled = false;
    let timer: number | undefined;
    let delay = INITIAL_POLL_DELAY_MS;
    const controller = new AbortController();

    const tick = async (): Promise<void> => {
      setLoading(true);
      setPolling(false);

      try {
        const data = await getDataset(datasetId, controller.signal);
        if (cancelled) return;

        setDataset(data);
        setError(null);
        setLoading(false);

        if (TERMINAL_STATUSES.has(data.status)) return;

        setPolling(true);
        timer = window.setTimeout(() => {
          void tick();
        }, delay);
        delay = Math.min(delay * 2, MAX_POLL_DELAY_MS);
      } catch (err) {
        if (cancelled || controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : "Failed to load dataset");
        setLoading(false);
        setPolling(false);
      }
    };

    void tick();

    return () => {
      cancelled = true;
      if (timer !== undefined) window.clearTimeout(timer);
      controller.abort();
    };
  }, [datasetId, reloadToken]);

  const refresh = useCallback(() => {
    setReloadToken((token) => token + 1);
  }, []);

  return { dataset, loading, error, polling, refresh };
}
