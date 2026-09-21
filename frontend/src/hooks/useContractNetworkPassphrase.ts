import { useEffect, useState } from "react";

/**
 * The passphrase the backend anchors to, once there is a reason to ask.
 *
 * `enabled` gates the request rather than the hook call: an anonymous visitor
 * has no wallet to compare against, so fetching `/health` on every page view
 * would be a request per page load for a comparison that cannot produce a
 * warning.
 */
export function useContractNetworkPassphrase(enabled: boolean): string | null {
  const [passphrase, setPassphrase] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled) return;

    let active = true;
    void (async () => {
      // Imported here rather than at the top of the file on purpose. This hook
      // hangs off `NetworkMismatchBanner`, which is part of the shell that every
      // page renders, so a static import would drag `api/client` — and axios
      // with it — into the entry chunk that the whole app waits on. The request
      // only happens once a wallet is connected, so the module can arrive with
      // it and the pages that need the client already load it.
      const { getContractNetworkPassphrase } = await import("../api/health");
      const value = await getContractNetworkPassphrase();
      // The component can unmount while the import or the request is in flight,
      // and the cache means a resolved value can arrive long after the first
      // mount.
      if (active) setPassphrase(value);
    })();

    return () => {
      active = false;
    };
  }, [enabled]);

  return passphrase;
}
