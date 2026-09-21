/** Stellar network configuration helpers. */

export const NETWORKS = {
  testnet: {
    passphrase: "Test SDF Network ; September 2015",
    rpcUrl: "https://soroban-testnet.stellar.org",
    explorerUrl: "https://stellar.expert/explorer/testnet",
  },
  mainnet: {
    passphrase: "Public Global Stellar Network ; September 2015",
    rpcUrl: "https://soroban.stellar.org",
    explorerUrl: "https://stellar.expert/explorer/public",
  },
} as const;

export type Network = keyof typeof NETWORKS;

export function getExplorerTxUrl(network: Network, txHash: string): string {
  return `${NETWORKS[network].explorerUrl}/tx/${txHash}`;
}

/**
 * Name a network by its passphrase, or `null` for one we do not know.
 *
 * The passphrase is the network's real identity — it is part of what a
 * signature commits to — so it is what comparisons are made on. This only turns
 * one back into a word for display; a custom network returns `null` rather than
 * being mislabelled as the nearest built-in one.
 */
export function networkFromPassphrase(passphrase: string | null | undefined): Network | null {
  if (!passphrase) return null;
  const entry = Object.entries(NETWORKS).find(([, config]) => config.passphrase === passphrase);
  return entry ? (entry[0] as Network) : null;
}
