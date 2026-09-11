import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

type WalletValue = {
  connected: boolean;
  publicKey: string | null;
  network: "testnet" | "mainnet" | null;
  networkPassphrase: string;
  error: string | null;
  connect: () => Promise<void>;
  disconnect: () => void;
  signTx: (xdr: string) => Promise<string>;
};

const wallet = vi.hoisted(() => ({
  value: {} as Record<string, unknown>,
}));

vi.mock("../../src/context/WalletContext", () => ({
  useWallet: () => wallet.value,
}));

import WalletConnector from "../../src/components/WalletConnector";

const PUBLIC_KEY = "GABCDEF12345678901234567890123456789012345678901234567890";

const connect = vi.fn<() => Promise<void>>();
const disconnect = vi.fn<() => void>();

function setWallet(overrides: Partial<WalletValue> = {}): WalletValue {
  const value: WalletValue = {
    connected: false,
    publicKey: null,
    network: null,
    networkPassphrase: "",
    error: null,
    connect,
    disconnect,
    signTx: vi.fn(),
    ...overrides,
  };
  wallet.value = value as unknown as Record<string, unknown>;
  return value;
}

describe("WalletConnector", () => {
  beforeEach(() => {
    connect.mockReset();
    disconnect.mockReset();
    connect.mockResolvedValue(undefined);
  });

  it("offers a connect button when disconnected", () => {
    setWallet();
    render(<WalletConnector />);

    expect(screen.getByText("Connect your Freighter wallet to get started.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Connect Freighter" })).toBeTruthy();
  });

  it("calls connect when the button is clicked", () => {
    setWallet();
    render(<WalletConnector />);

    fireEvent.click(screen.getByRole("button", { name: "Connect Freighter" }));

    expect(connect).toHaveBeenCalledTimes(1);
  });

  it("hides the helper text in compact mode", () => {
    setWallet();
    render(<WalletConnector compact />);

    expect(screen.queryByText(/Connect your Freighter wallet to get started/)).toBeNull();
    expect(screen.getByRole("button", { name: "Connect Freighter" })).toBeTruthy();
  });

  it("shows a truncated address and network when connected", () => {
    setWallet({ connected: true, publicKey: PUBLIC_KEY, network: "testnet" });
    render(<WalletConnector />);

    expect(screen.getByText(`${PUBLIC_KEY.slice(0, 6)}...${PUBLIC_KEY.slice(-4)}`)).toBeTruthy();
    expect(screen.getByText("testnet")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Connect Freighter" })).toBeNull();
  });

  it("highlights mainnet differently from testnet", () => {
    setWallet({ connected: true, publicKey: PUBLIC_KEY, network: "mainnet" });
    render(<WalletConnector />);

    expect(screen.getByText("mainnet").className).toContain("bg-blue-100");
  });

  it("calls disconnect when connected", () => {
    setWallet({ connected: true, publicKey: PUBLIC_KEY, network: "testnet" });
    render(<WalletConnector />);

    fireEvent.click(screen.getByRole("button", { name: "Disconnect" }));

    expect(disconnect).toHaveBeenCalledTimes(1);
  });

  it("surfaces wallet errors", () => {
    setWallet({ error: "Freighter is not installed" });
    render(<WalletConnector />);

    expect(screen.getByText("Freighter is not installed")).toBeTruthy();
  });

  it("does not treat a connected state without a public key as connected", () => {
    setWallet({ connected: true, publicKey: null });
    render(<WalletConnector />);

    expect(screen.getByRole("button", { name: "Connect Freighter" })).toBeTruthy();
  });
});
