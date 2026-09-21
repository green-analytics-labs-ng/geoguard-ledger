import { useState, useEffect, useCallback, useRef } from "react";
import { verifyByHash, verifyByFile, verifyById } from "../api/verify";
import type { VerifyResult } from "../types";

interface UseVerifyReturn {
  result: VerifyResult | null;
  loading: boolean;
  error: string | null;
  verify: (input: string | File) => Promise<void>;
  clear: () => void;
}

export function useVerify(): UseVerifyReturn {
  const [result, setResult] = useState<VerifyResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Same contract as `useDatasets`: a second verification supersedes the first,
  // and unmounting drops whatever is still running.
  const requestRef = useRef<AbortController | null>(null);

  const verify = useCallback(async (input: string | File) => {
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    const { signal } = controller;

    setLoading(true);
    setError(null);
    setResult(null);
    try {
      let res: VerifyResult;
      if (input instanceof File) {
        res = await verifyByFile(input, signal);
      } else if (input.length === 64) {
        res = await verifyByHash(input, signal);
      } else {
        res = await verifyById(input, signal);
      }
      setResult(res);
    } catch (err) {
      if (signal.aborted) return;
      const message = err instanceof Error ? err.message : "Verification failed";
      setError(message);
    } finally {
      if (!signal.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => () => requestRef.current?.abort(), []);

  const clear = useCallback(() => {
    setResult(null);
    setError(null);
  }, []);

  return { result, loading, error, verify, clear };
}
