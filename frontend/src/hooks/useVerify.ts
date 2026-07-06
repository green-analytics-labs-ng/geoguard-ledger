import { useState, useCallback } from "react";
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

  const verify = useCallback(async (input: string | File) => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      let res: VerifyResult;
      if (input instanceof File) {
        res = await verifyByFile(input);
      } else if (input.length === 64) {
        res = await verifyByHash(input);
      } else {
        res = await verifyById(input);
      }
      setResult(res);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Verification failed";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  const clear = useCallback(() => {
    setResult(null);
    setError(null);
  }, []);

  return { result, loading, error, verify, clear };
}
