import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const wallet = vi.hoisted(() => ({ value: {} as Record<string, unknown> }));

vi.mock("../../src/context/WalletContext", () => ({
  useWallet: () => wallet.value,
}));

const datasetsApi = vi.hoisted(() => ({
  uploadCsv: vi.fn(),
  anchorDataset: vi.fn(),
  submitDataset: vi.fn(),
}));

vi.mock("../../src/api/datasets", () => datasetsApi);

import SingleAnchorFlow from "../../src/components/SingleAnchorFlow";
import type {
  DatasetAnchorResponse,
  DatasetCreateResponse,
} from "../../src/types";

const PUBLIC_KEY = `G${"A".repeat(55)}`;
const HASH = "1".repeat(64);
const SUMMARY = "[NORMAL] Score=10.0%, 0/6 rows flagged (0.0%).";
const UNSIGNED_XDR = "AAAAUNSIGNED";
const SIGNED_XDR = "AAAASIGNED";

const signTx = vi.fn<(xdr: string) => Promise<string>>();
const connect = vi.fn<() => Promise<void>>();

function setWallet(overrides: Record<string, unknown> = {}): void {
  wallet.value = {
    connected: true,
    publicKey: PUBLIC_KEY,
    network: "testnet",
    networkPassphrase: "Test SDF Network ; September 2015",
    error: null,
    connect,
    disconnect: vi.fn(),
    signTx,
    ...overrides,
  };
}

function analyzeResponse(): DatasetCreateResponse {
  return {
    dataset_id: "d1",
    dataset_hash: HASH,
    anomaly_report: {
      score: 0.1,
      flags: [],
      model_version: "isoforest_v1",
      summary: SUMMARY,
    },
    created_at: "2026-09-12T00:00:00Z",
  };
}

function anchorResponse(): DatasetAnchorResponse {
  return {
    dataset_id: "d1",
    dataset_hash: HASH,
    unsigned_transaction_xdr: UNSIGNED_XDR,
  };
}

function renderFlow() {
  return render(
    <MemoryRouter>
      <SingleAnchorFlow />
    </MemoryRouter>,
  );
}

function selectFile(container: HTMLElement, name = "site-a.csv"): void {
  const input = container.querySelector('input[type="file"]');
  if (!(input instanceof HTMLInputElement)) {
    throw new Error("file input not found");
  }
  fireEvent.change(input, {
    target: {
      files: [new File(["pH,conductivity\n7.2,450\n"], name, { type: "text/csv" })],
    },
  });
}

/** Drop a file and wait for the preview step, which is where processing starts. */
async function reachPreviewStep(container: HTMLElement): Promise<void> {
  selectFile(container);
  await screen.findByText(/Review the data preview below/);
}

/** Analyze the file and land on the AI report step. */
async function reachReportStep(container: HTMLElement): Promise<void> {
  await reachPreviewStep(container);
  datasetsApi.uploadCsv.mockResolvedValueOnce(analyzeResponse());
  fireEvent.click(
    screen.getByRole("button", { name: "Process & Detect Anomalies" }),
  );
  await screen.findByText(SUMMARY);
}

const CONNECT_PROMPT = "Connect your Freighter wallet to anchor this dataset";

describe("SingleAnchorFlow", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    setWallet();
    signTx.mockResolvedValue(SIGNED_XDR);
    connect.mockResolvedValue(undefined);
  });

  it("analyzes the dataset without a wallet", async () => {
    setWallet({ connected: false, publicKey: null });
    const { container } = renderFlow();
    await reachPreviewStep(container);

    // Hashing and scoring are not signed, so no wallet is asked for yet.
    const processButton = screen.getByRole("button", {
      name: "Process & Detect Anomalies",
    });
    expect(processButton.hasAttribute("disabled")).toBe(false);
    expect(screen.queryByRole("button", { name: CONNECT_PROMPT })).toBeNull();

    datasetsApi.uploadCsv.mockResolvedValueOnce(analyzeResponse());
    fireEvent.click(processButton);

    expect(await screen.findByText(SUMMARY)).toBeTruthy();
    expect(datasetsApi.uploadCsv).toHaveBeenCalledTimes(1);
    // The upload carries the file only: there is no address at this point.
    expect(datasetsApi.uploadCsv.mock.calls[0]).toHaveLength(1);
  });

  it("asks for a wallet only when there is a transaction to sign", async () => {
    setWallet({ connected: false, publicKey: null });
    const { container } = renderFlow();
    await reachReportStep(container);

    const signButton = screen.getByRole("button", {
      name: "Connect Wallet First",
    });
    expect(signButton.hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("button", { name: CONNECT_PROMPT })).toBeTruthy();
    // No transaction has been requested, so nothing is waiting to be signed.
    expect(datasetsApi.anchorDataset).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: CONNECT_PROMPT }));

    expect(connect).toHaveBeenCalledTimes(1);
  });

  it("anchors the dataset on the way to the sign step", async () => {
    const { container } = renderFlow();
    await reachReportStep(container);

    datasetsApi.anchorDataset.mockResolvedValueOnce(anchorResponse());
    fireEvent.click(screen.getByRole("button", { name: "Continue to Sign" }));

    expect(await screen.findByText(/sign with your Freighter wallet/)).toBeTruthy();
    expect(datasetsApi.anchorDataset).toHaveBeenCalledWith("d1", PUBLIC_KEY);
  });

  it("surfaces a failure to build the anchoring transaction", async () => {
    const { container } = renderFlow();
    await reachReportStep(container);

    datasetsApi.anchorDataset.mockRejectedValueOnce(new Error("RPC unavailable"));
    fireEvent.click(screen.getByRole("button", { name: "Continue to Sign" }));

    expect(await screen.findByText("RPC unavailable")).toBeTruthy();
    // The report is still on screen, so the researcher can retry.
    expect(screen.queryByText(/sign with your Freighter wallet/)).toBeNull();
  });

  it("signs the transaction that anchoring produced and submits it", async () => {
    const { container } = renderFlow();
    await reachReportStep(container);
    datasetsApi.anchorDataset.mockResolvedValueOnce(anchorResponse());
    fireEvent.click(screen.getByRole("button", { name: "Continue to Sign" }));
    await screen.findByText(/sign with your Freighter wallet/);

    datasetsApi.submitDataset.mockResolvedValueOnce({
      dataset_id: "d1",
      status: "anchored",
      stellar_tx_hash: "T".repeat(64),
      ledger_number: 42,
      explorer_url: `https://stellar.expert/explorer/testnet/tx/${"T".repeat(64)}`,
      anchored_at: "2026-09-12T00:00:00Z",
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Sign & Anchor to Stellar" }),
    );

    expect(await screen.findByText("Dataset Anchored!")).toBeTruthy();
    // The signed envelope is the one built by the anchor step, not a stale one.
    expect(signTx).toHaveBeenCalledWith(UNSIGNED_XDR);
    expect(datasetsApi.submitDataset).toHaveBeenCalledWith("d1", SIGNED_XDR);
    expect(screen.getByText("#42")).toBeTruthy();
  });

  it("clears the built transaction when the flow is reset", async () => {
    const { container } = renderFlow();
    await reachReportStep(container);
    datasetsApi.anchorDataset.mockResolvedValueOnce(anchorResponse());
    fireEvent.click(screen.getByRole("button", { name: "Continue to Sign" }));
    await screen.findByText(/sign with your Freighter wallet/);

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.getByText(/Drop a CSV, JSON, or XML file here/)).toBeTruthy();
    expect(screen.queryByText(/sign with your Freighter wallet/)).toBeNull();
  });
});
