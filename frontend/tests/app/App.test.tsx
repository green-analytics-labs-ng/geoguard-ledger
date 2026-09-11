/**
 * Routing integration tests.
 *
 * `App.tsx` renders the route table from `routes.tsx` inside an
 * `ErrorBoundary` and a `WalletProvider`. Freighter is mocked so the app can
 * mount in jsdom without a wallet extension.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

const freighter = vi.hoisted(() => ({
  isAllowed: vi.fn(),
  isConnected: vi.fn(),
  getAddress: vi.fn(),
  getNetwork: vi.fn(),
  signTransaction: vi.fn(),
  requestAccess: vi.fn(),
}));

vi.mock("@stellar/freighter-api", () => freighter);

import App from "../../src/App";

function goTo(path: string): void {
  window.history.pushState({}, "", path);
}

describe("App routing", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    freighter.isAllowed.mockResolvedValue({ isAllowed: false });
    freighter.isConnected.mockResolvedValue({ isConnected: false });
    freighter.getAddress.mockResolvedValue({ address: "" });
    freighter.getNetwork.mockResolvedValue({
      network: "TESTNET",
      networkPassphrase: "Test SDF Network ; September 2015",
    });
    freighter.requestAccess.mockResolvedValue({});
    freighter.signTransaction.mockResolvedValue({ signedTxXdr: "" });
  });

  it("renders the dashboard at the root path", async () => {
    goTo("/");
    render(<App />);

    expect(await screen.findByRole("heading", { name: "GeoGuard Ledger" })).toBeTruthy();
  });

  it("renders the upload page at /upload", async () => {
    goTo("/upload");
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Upload Dataset" })).toBeTruthy();
    expect(screen.getByText(/Drop a .*file here/i)).toBeTruthy();
  });

  it("renders the verify page at /verify", async () => {
    goTo("/verify");
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Verify Dataset" })).toBeTruthy();
  });

  it("renders the settings page at /settings", async () => {
    goTo("/settings");
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Settings" })).toBeTruthy();
  });

  it("still mounts when Freighter is unavailable", async () => {
    goTo("/");
    freighter.isAllowed.mockRejectedValue(new Error("Freighter not installed"));

    render(<App />);

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "GeoGuard Ledger" })).toBeTruthy(),
    );
  });
});
