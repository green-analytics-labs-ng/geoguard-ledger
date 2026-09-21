import client from "./client";

/**
 * The network passphrase the backend builds and verifies transactions against.
 *
 * Read from `GET /health` rather than configured in the frontend. The anchor
 * transaction is built server-side, so the backend's passphrase is the only
 * thing that decides which signature will be accepted; a frontend copy (an env
 * var, say) could disagree with it and the disagreement would be invisible
 * until a submission was rejected without explanation.
 *
 * A failure resolves to `null`, which callers treat as "unknown" and stay quiet
 * about. Warning on a guess would be worse than not warning: an unreachable
 * health endpoint says nothing about the wallet.
 */
let cached: Promise<string | null> | null = null;

export function getContractNetworkPassphrase(): Promise<string | null> {
  cached ??= client
    .get("/health")
    .then((response) => {
      const passphrase = response.data?.network_passphrase;
      return typeof passphrase === "string" ? passphrase : null;
    })
    .catch(() => null);

  return cached;
}

/** Test seam: forget the cached answer so the next call fetches again. */
export function resetContractNetworkPassphrase(): void {
  cached = null;
}
