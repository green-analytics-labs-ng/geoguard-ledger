import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ROUTER_FUTURE_FLAGS } from "../../src/routerConfig";

const wallet = vi.hoisted(() => ({ value: {} as Record<string, unknown> }));

vi.mock("../../src/context/WalletContext", () => ({
  useWallet: () => wallet.value,
}));

const verifyApi = vi.hoisted(() => ({
  verifyByHash: vi.fn(),
  verifyByFile: vi.fn(),
  verifyById: vi.fn(),
}));

vi.mock("../../src/api/verify", () => verifyApi);

import VerifyPage from "../../src/pages/VerifyPage";

const HASH = "a".repeat(64);

const MATCH = {
  match: true,
  on_chain_record: {
    dataset_hash: HASH,
    anomaly_score: 0,
    model_version: "isoforest_v1",
    timestamp: 1751715300,
    submitter: "GABC",
  },
  local_record: null,
};

function renderPage(entry = "/verify") {
  return render(
    <MemoryRouter future={ROUTER_FUTURE_FLAGS} initialEntries={[entry]}>
      <VerifyPage />
    </MemoryRouter>,
  );
}

function hashInput(): HTMLInputElement {
  const input = screen.getByPlaceholderText(/Paste a 64-character hex hash/);
  if (!(input instanceof HTMLInputElement))
    throw new Error("hash input not found");
  return input;
}

describe("VerifyPage linked hash", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    wallet.value = {
      connected: false,
      publicKey: null,
      network: null,
      networkPassphrase: "",
      error: null,
      connect: vi.fn(),
      disconnect: vi.fn(),
      signTx: vi.fn(),
    };
    verifyApi.verifyByHash.mockResolvedValue(MATCH);
  });

  it("does not verify anything on a plain visit", () => {
    renderPage();

    expect(verifyApi.verifyByHash).not.toHaveBeenCalled();
    expect(hashInput().value).toBe("");
  });

  it("prefills and verifies a hash supplied in the query string", async () => {
    renderPage(`/verify?dataset_hash=${HASH}`);

    await waitFor(() =>
      expect(verifyApi.verifyByHash).toHaveBeenCalledWith(HASH),
    );
    expect(hashInput().value).toBe(HASH);
    expect(screen.getByText("Dataset Verified")).toBeTruthy();
  });

  it("ignores a malformed linked hash", () => {
    renderPage("/verify?dataset_hash=not-a-hash");

    expect(verifyApi.verifyByHash).not.toHaveBeenCalled();
  });
});
