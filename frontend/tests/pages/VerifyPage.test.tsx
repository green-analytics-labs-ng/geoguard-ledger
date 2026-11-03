import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

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
    <MemoryRouter initialEntries={[entry]}>
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

    // The signal is part of the call: a verification that is superseded or
    // unmounted has to be cancellable, so the page always passes one.
    await waitFor(() =>
      expect(verifyApi.verifyByHash).toHaveBeenCalledWith(HASH, expect.any(AbortSignal)),
    );
    expect(hashInput().value).toBe(HASH);
    expect(screen.getByText("Dataset Verified")).toBeTruthy();
  });

  it("ignores a malformed linked hash", () => {
    renderPage("/verify?dataset_hash=not-a-hash");

    expect(verifyApi.verifyByHash).not.toHaveBeenCalled();
  });
});

describe("VerifyPage accessible names", () => {
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
  });

  it("associates the hash label with its input", () => {
    renderPage();

    // Found by its label rather than its placeholder: a placeholder is a hint,
    // not a name, and it disappears as soon as the user types.
    expect(screen.getByLabelText("Dataset Hash (SHA-256)")).toBe(hashInput());
  });

  it("associates the file label with the file input", () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "By File Upload" }));

    const input = screen.getByLabelText("Upload a data file to re-compute its hash");
    expect(input).toBeInstanceOf(HTMLInputElement);
    expect((input as HTMLInputElement).type).toBe("file");
  });
});
