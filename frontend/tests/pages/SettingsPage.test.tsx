import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ROUTER_FUTURE_FLAGS } from "../../src/routerConfig";

const wallet = vi.hoisted(() => ({ value: {} as Record<string, unknown> }));

vi.mock("../../src/context/WalletContext", () => ({
  useWallet: () => wallet.value,
}));

import SettingsPage from "../../src/pages/SettingsPage";
import { getApiKey } from "../../src/api/apiKey";

const STORAGE_KEY = "geoguard.apiKey";

function renderPage() {
  return render(
    <MemoryRouter future={ROUTER_FUTURE_FLAGS} initialEntries={["/settings"]}>
      <SettingsPage />
    </MemoryRouter>,
  );
}

function apiKeyInput(): HTMLInputElement {
  const input = screen.getByLabelText("API Key");
  if (!(input instanceof HTMLInputElement)) throw new Error("API key input not found");
  return input;
}

describe("SettingsPage API key", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    localStorage.clear();
    wallet.value = {
      connected: false,
      publicKey: null,
      network: "testnet",
      networkPassphrase: "",
      error: null,
      connect: vi.fn(),
      disconnect: vi.fn(),
      signTx: vi.fn(),
    };
  });

  it("starts empty with nothing to clear", () => {
    renderPage();

    expect(apiKeyInput().value).toBe("");
    expect(screen.queryByRole("button", { name: "Clear" })).toBeNull();
  });

  it("saves the entered key for later requests", () => {
    renderPage();
    fireEvent.change(apiKeyInput(), { target: { value: "my-key" } });

    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(getApiKey()).toBe("my-key");
    expect(screen.getByText("API key saved.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Clear" })).toBeTruthy();
  });

  it("trims the key before saving", () => {
    renderPage();
    fireEvent.change(apiKeyInput(), { target: { value: "  my-key  " } });

    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(getApiKey()).toBe("my-key");
  });

  it("reports an already-configured key and clears it", () => {
    localStorage.setItem(STORAGE_KEY, "existing-key");
    renderPage();

    expect(screen.getByText("A key is configured for this browser.")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Clear" }));

    expect(getApiKey()).toBe("");
    expect(screen.queryByRole("button", { name: "Clear" })).toBeNull();
  });
});
