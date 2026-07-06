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
