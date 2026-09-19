import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ROUTER_FUTURE_FLAGS } from "../../src/routerConfig";

const wallet = vi.hoisted(() => ({ value: {} as Record<string, unknown> }));

vi.mock("../../src/context/WalletContext", () => ({
  useWallet: () => wallet.value,
}));

const datasetsApi = vi.hoisted(() => ({
  uploadCsv: vi.fn(),
  submitDataset: vi.fn(),
}));

vi.mock("../../src/api/datasets", () => datasetsApi);

const batchesApi = vi.hoisted(() => ({
  createBatch: vi.fn(),
  submitBatch: vi.fn(),
  listBatches: vi.fn(),
  getBatch: vi.fn(),
}));

vi.mock("../../src/api/batches", () => batchesApi);

import BatchAnchorFlow from "../../src/components/BatchAnchorFlow";
import type {
  BatchCreateResponse,
  DatasetCreateResponse,
} from "../../src/types";

const PUBLIC_KEY = `G${"A".repeat(55)}`;
const HASH_1 = "1".repeat(64);
const HASH_2 = "2".repeat(64);
const ROOT = "3".repeat(64);
const SIBLING = "4".repeat(64);
const SIGNED_XDR = "SIGNEDXDR";

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

function dataset(id: string, hash: string, score = 0.1): DatasetCreateResponse {
  return {
    dataset_id: id,
    dataset_hash: hash,
    anomaly_report: {
      score,
      flags: [],
      model_version: "isoforest_v1",
      summary: "[NORMAL] Score=10.0%, 0/6 rows flagged (0.0%).",
    },
    created_at: "2026-09-12T00:00:00Z",
  };
}

function batchResponse(): BatchCreateResponse {
  return {
    batch_id: "batch-1",
    merkle_root: ROOT,
    leaf_count: 2,
    unsigned_transaction_xdr: "ROOTXDR",
    leaves: [
      {
        dataset_id: "d1",
        dataset_hash: HASH_1,
        leaf_index: 0,
        merkle_proof: [SIBLING],
        anomaly_score: 0.1,
      },
      {
        dataset_id: "d2",
        dataset_hash: HASH_2,
        leaf_index: 1,
        merkle_proof: [SIBLING],
        anomaly_score: 0.2,
      },
    ],
    created_at: "2026-09-12T00:00:00Z",
  };
}

function renderFlow() {
  return render(
    <MemoryRouter future={ROUTER_FUTURE_FLAGS}>
      <BatchAnchorFlow />
    </MemoryRouter>,
  );
}

function fileInput(container: HTMLElement): HTMLInputElement {
  const input = container.querySelector('input[type="file"]');
  if (!(input instanceof HTMLInputElement)) {
    throw new Error("file input not found");
  }
  return input;
}

function selectFile(container: HTMLElement, name = "site-a.csv"): void {
  fireEvent.change(fileInput(container), {
    target: {
      files: [
        new File(["pH,conductivity\n7.2,450\n"], name, { type: "text/csv" }),
      ],
    },
  });
}

async function addDataset(
  container: HTMLElement,
  name: string,
  response: DatasetCreateResponse,
): Promise<void> {
  datasetsApi.uploadCsv.mockResolvedValueOnce(response);
  selectFile(container, name);
  fireEvent.click(await screen.findByRole("button", { name: "Add to Batch" }));
  await waitFor(() =>
    expect(screen.getByText(response.dataset_hash)).toBeTruthy(),
  );
}

async function readyToAnchor(container: HTMLElement): Promise<void> {
  await addDataset(container, "site-a.csv", dataset("d1", HASH_1));
  await addDataset(container, "site-b.csv", dataset("d2", HASH_2));
  batchesApi.createBatch.mockResolvedValueOnce(batchResponse());
  fireEvent.click(screen.getByRole("button", { name: "Review Batch" }));
  fireEvent.click(screen.getByRole("button", { name: "Create Merkle Root" }));
  await screen.findByText(ROOT);
}

describe("BatchAnchorFlow", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    setWallet();
    signTx.mockResolvedValue(SIGNED_XDR);
    connect.mockResolvedValue(undefined);
  });

  it("starts with an empty batch and no review action", () => {
    const { container } = renderFlow();

    expect(screen.getByText(/No datasets added yet/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Review Batch" })).toBeNull();
    expect(fileInput(container)).toBeTruthy();
  });

  it("adds an uploaded dataset to the batch", async () => {
    const { container } = renderFlow();

    await addDataset(container, "site-a.csv", dataset("d1", HASH_1));

    expect(datasetsApi.uploadCsv).toHaveBeenCalledTimes(1);
    // The file is the only argument: analysis needs no address, and the batch
    // root transaction is what binds the submitter.
    expect(datasetsApi.uploadCsv.mock.calls[0]).toHaveLength(1);
    expect(screen.getByText("1 dataset")).toBeTruthy();
    expect(screen.getByText("site-a.csv")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Review Batch" })).toBeTruthy();
  });

  it("removes a member before the root is created", async () => {
    const { container } = renderFlow();
    await addDataset(container, "site-a.csv", dataset("d1", HASH_1));

    fireEvent.click(screen.getByRole("button", { name: "Remove" }));

    expect(screen.queryByText(HASH_1)).toBeNull();
    expect(screen.getByText(/No datasets added yet/)).toBeTruthy();
  });

  it("reviews the batch without contacting the backend", async () => {
    const { container } = renderFlow();
    await addDataset(container, "site-a.csv", dataset("d1", HASH_1));
    await addDataset(container, "site-b.csv", dataset("d2", HASH_2));

    fireEvent.click(screen.getByRole("button", { name: "Review Batch" }));

    expect(screen.getByText("2 datasets")).toBeTruthy();
    expect(screen.getByText(/single Merkle root/)).toBeTruthy();
    expect(batchesApi.createBatch).not.toHaveBeenCalled();
  });

  it("can return to add another dataset from the review step", async () => {
    const { container } = renderFlow();
    await addDataset(container, "site-a.csv", dataset("d1", HASH_1));
    fireEvent.click(screen.getByRole("button", { name: "Review Batch" }));

    fireEvent.click(
      screen.getByRole("button", { name: "Add Another Dataset" }),
    );

    expect(screen.getByRole("button", { name: "Review Batch" })).toBeTruthy();
    expect(fileInput(container)).toBeTruthy();
  });

  it("creates the Merkle root in the order datasets were added", async () => {
    const { container } = renderFlow();

    await readyToAnchor(container);

    expect(batchesApi.createBatch).toHaveBeenCalledWith(PUBLIC_KEY, [
      "d1",
      "d2",
    ]);
    expect(screen.getByText("Merkle Batch Summary")).toBeTruthy();
    expect(screen.getByText("2 leaves")).toBeTruthy();
    expect(screen.getByText("Leaf 0")).toBeTruthy();
    expect(screen.getByText("Leaf 1")).toBeTruthy();
    expect(screen.getByText(/Continue to Sign/)).toBeTruthy();
  });

  it("surfaces the backend detail when the root cannot be created", async () => {
    const { container } = renderFlow();
    await addDataset(container, "site-a.csv", dataset("d1", HASH_1));
    fireEvent.click(screen.getByRole("button", { name: "Review Batch" }));

    batchesApi.createBatch.mockRejectedValueOnce({
      response: {
        data: { detail: "Datasets already anchored in a batch: d1" },
      },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create Merkle Root" }));

    expect(
      await screen.findByText("Datasets already anchored in a batch: d1"),
    ).toBeTruthy();
  });

  it("surfaces an upload failure", async () => {
    const { container } = renderFlow();
    datasetsApi.uploadCsv.mockRejectedValueOnce(new Error("File too large"));

    selectFile(container);
    fireEvent.click(
      await screen.findByRole("button", { name: "Add to Batch" }),
    );

    expect(await screen.findByText("File too large")).toBeTruthy();
    expect(screen.getByText(/No datasets added yet/)).toBeTruthy();
  });

  it("anchors the whole batch with a single signature", async () => {
    const { container } = renderFlow();
    await readyToAnchor(container);

    fireEvent.click(screen.getByRole("button", { name: "Continue to Sign" }));
    batchesApi.submitBatch.mockResolvedValueOnce({
      batch_id: "batch-1",
      status: "anchored",
      stellar_tx_hash: "T".repeat(64),
      ledger_number: 42,
      explorer_url:
        "https://stellar.expert/explorer/testnet/tx/" + "T".repeat(64),
      anchored_at: "2026-09-12T00:00:00Z",
    });

    fireEvent.click(
      screen.getByRole("button", { name: "Sign & Anchor Batch" }),
    );

    expect(await screen.findByText("Batch Anchored!")).toBeTruthy();
    expect(signTx).toHaveBeenCalledWith("ROOTXDR");
    expect(batchesApi.submitBatch).toHaveBeenCalledWith("batch-1", SIGNED_XDR);
    expect(screen.getByText("#42")).toBeTruthy();
    expect(screen.getByText(ROOT)).toBeTruthy();
    // One inclusion proof per dataset.
    expect(screen.getByText("Inclusion Proofs")).toBeTruthy();
    expect(screen.getAllByText(SIBLING)).toHaveLength(2);
    expect(
      screen.getAllByRole("button", { name: "Verify proof" }),
    ).toHaveLength(2);
  });

  it("keeps the batch recoverable when the signature is rejected", async () => {
    const { container } = renderFlow();
    await readyToAnchor(container);

    fireEvent.click(screen.getByRole("button", { name: "Continue to Sign" }));
    signTx.mockRejectedValueOnce(new Error("User rejected the request"));

    fireEvent.click(
      screen.getByRole("button", { name: "Sign & Anchor Batch" }),
    );

    expect(
      await screen.findByText(
        "Transaction was rejected in Freighter. Please try again.",
      ),
    ).toBeTruthy();
    expect(batchesApi.submitBatch).not.toHaveBeenCalled();
    // The user can try signing the same batch again.
    expect(
      screen.getByRole("button", { name: "Sign & Anchor Batch" }),
    ).toBeTruthy();
  });

  it("resets the flow after anchoring", async () => {
    const { container } = renderFlow();
    await readyToAnchor(container);
    fireEvent.click(screen.getByRole("button", { name: "Continue to Sign" }));
    batchesApi.submitBatch.mockResolvedValueOnce({
      batch_id: "batch-1",
      status: "anchored",
      stellar_tx_hash: "T".repeat(64),
      ledger_number: 42,
      explorer_url: "https://example.test",
      anchored_at: "2026-09-12T00:00:00Z",
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Sign & Anchor Batch" }),
    );
    await screen.findByText("Batch Anchored!");

    fireEvent.click(screen.getByRole("button", { name: "Start a New Batch" }));

    expect(screen.getByText(/No datasets added yet/)).toBeTruthy();
    expect(screen.queryByText("Batch Anchored!")).toBeNull();
  });

  it("collects and reviews datasets before any wallet is connected", async () => {
    setWallet({ connected: false, publicKey: null });
    const { container } = renderFlow();

    await addDataset(container, "site-a.csv", dataset("d1", HASH_1));

    expect(datasetsApi.uploadCsv).toHaveBeenCalledTimes(1);
    expect(screen.getByText("site-a.csv")).toBeTruthy();
    expect(screen.getByText("1 dataset")).toBeTruthy();

    // Reviewing is local, so a wallet is still not needed here.
    fireEvent.click(screen.getByRole("button", { name: "Review Batch" }));

    expect(screen.getByText(/single Merkle root/)).toBeTruthy();
  });

  it("requires a wallet to build the Merkle root", async () => {
    setWallet({ connected: false, publicKey: null });
    const { container } = renderFlow();
    await addDataset(container, "site-a.csv", dataset("d1", HASH_1));
    fireEvent.click(screen.getByRole("button", { name: "Review Batch" }));

    const rootButton = screen.getByRole("button", {
      name: "Connect Wallet First",
    });
    expect(rootButton.hasAttribute("disabled")).toBe(true);
    expect(
      screen.getByRole("button", {
        name: "Connect your Freighter wallet to build the Merkle root",
      }),
    ).toBeTruthy();
    expect(batchesApi.createBatch).not.toHaveBeenCalled();
  });
});
