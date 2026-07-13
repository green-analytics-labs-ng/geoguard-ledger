import { describe, it, expect } from "vitest";
import {
  NETWORKS,
  type Network,
  getExplorerTxUrl,
} from "../../src/utils/stellar";

describe("NETWORKS", () => {
  it("has testnet and mainnet entries", () => {
    expect(NETWORKS).toHaveProperty("testnet");
    expect(NETWORKS).toHaveProperty("mainnet");
  });

  it("testnet has correct passphrase", () => {
    expect(NETWORKS.testnet.passphrase).toBe(
      "Test SDF Network ; September 2015",
    );
  });

  it("mainnet has correct passphrase", () => {
    expect(NETWORKS.mainnet.passphrase).toBe(
      "Public Global Stellar Network ; September 2015",
    );
  });

  it("testnet has the expected rpcUrl", () => {
    expect(NETWORKS.testnet.rpcUrl).toBe(
      "https://soroban-testnet.stellar.org",
    );
  });

  it("mainnet has the expected rpcUrl", () => {
    expect(NETWORKS.mainnet.rpcUrl).toBe("https://soroban.stellar.org");
  });

  it("testnet has the expected explorerUrl", () => {
    expect(NETWORKS.testnet.explorerUrl).toBe(
      "https://stellar.expert/explorer/testnet",
    );
  });

  it("mainnet has the expected explorerUrl", () => {
    expect(NETWORKS.mainnet.explorerUrl).toBe(
      "https://stellar.expert/explorer/public",
    );
  });

  it("only has the two known networks (no accidental additions)", () => {
    expect(Object.keys(NETWORKS)).toEqual(["testnet", "mainnet"]);
  });
});

describe("Network type", () => {
  it("accepts 'testnet'", () => {
    const n: Network = "testnet";
    expect(n).toBe("testnet");
  });

  it("accepts 'mainnet'", () => {
    const n: Network = "mainnet";
    expect(n).toBe("mainnet");
  });
});

describe("getExplorerTxUrl", () => {
  it("builds a testnet tx URL", () => {
    const url = getExplorerTxUrl(
      "testnet",
      "abc123def456abc123def456abc123def456abc123def456abc123def456abc123",
    );
    expect(url).toBe(
      "https://stellar.expert/explorer/testnet/tx/abc123def456abc123def456abc123def456abc123def456abc123def456abc123",
    );
  });

  it("builds a mainnet tx URL", () => {
    const url = getExplorerTxUrl(
      "mainnet",
      "abc123def456abc123def456abc123def456abc123def456abc123def456abc123",
    );
    expect(url).toBe(
      "https://stellar.expert/explorer/public/tx/abc123def456abc123def456abc123def456abc123def456abc123def456abc123",
    );
  });

  it("handles a short tx hash", () => {
    const url = getExplorerTxUrl("testnet", "abc123");
    expect(url).toBe("https://stellar.expert/explorer/testnet/tx/abc123");
  });

  it("handles an empty tx hash (degenerate)", () => {
    const url = getExplorerTxUrl("testnet", "");
    expect(url).toBe("https://stellar.expert/explorer/testnet/tx/");
  });
});
