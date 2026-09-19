import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { ROUTER_FUTURE_FLAGS } from "../../src/routerConfig";

const wallet = vi.hoisted(() => ({ value: {} as Record<string, unknown> }));

vi.mock("../../src/context/WalletContext", () => ({
  useWallet: () => wallet.value,
}));

const datasetsApi = vi.hoisted(() => ({
  getDataset: vi.fn(),
  listDatasets: vi.fn(),
  uploadCsv: vi.fn(),
  submitDataset: vi.fn(),
}));

vi.mock("../../src/api/datasets", () => datasetsApi);

import DatasetDetailPage from "../../src/pages/DatasetDetailPage";
import type { DatasetResponse } from "../../src/types";

const HASH = "a".repeat(64);
const TX_HASH = "b".repeat(64);
const ROOT = "f".repeat(64);
const SIBLING = "c".repeat(64);

function makeDataset(
  overrides: Partial<DatasetResponse> = {},
): DatasetResponse {
  return {
    dataset_id: "ds-1",
    dataset_hash: HASH,
    status: "anchored",
    anomaly_score: 0.12,
    stellar_tx_hash: TX_HASH,
    created_at: "2026-07-05T12:00:00Z",
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter future={ROUTER_FUTURE_FLAGS} initialEntries={["/datasets/ds-1"]}>
      <Routes>
        <Route path="/datasets/:id" element={<DatasetDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

async function renderWith(dataset: DatasetResponse) {
  datasetsApi.getDataset.mockResolvedValue(dataset);
  renderPage();
  await waitFor(() => expect(screen.getByText("Dataset Details")).toBeTruthy());
  return dataset;
}

describe("DatasetDetailPage batch membership", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    wallet.value = { connected: false, publicKey: null, network: "testnet" };
  });

  it("shows a standalone dataset without a batch section", async () => {
    await renderWith(makeDataset());

    expect(screen.queryByText("Batch Membership")).toBeNull();
    expect(screen.queryByText("Merkle Inclusion Proof")).toBeNull();
    expect(screen.getByText("Transaction")).toBeTruthy();
  });

  it("surfaces the batch root, leaf position and sibling path", async () => {
    await renderWith(
      makeDataset({
        batch_id: "batch-1",
        merkle_root: ROOT,
        leaf_index: 2,
        merkle_proof: [SIBLING],
      }),
    );

    expect(screen.getByText("Batch Membership")).toBeTruthy();
    expect(screen.getByText("Merkle Inclusion Proof")).toBeTruthy();
    expect(screen.getByText(ROOT)).toBeTruthy();
    expect(screen.getByText(SIBLING)).toBeTruthy();
    expect(screen.getByText("1 sibling")).toBeTruthy();
    expect(screen.getByText("batch-1")).toBeTruthy();
  });

  it("marks the dataset as batched in the header", async () => {
    await renderWith(
      makeDataset({
        batch_id: "batch-1",
        merkle_root: ROOT,
        leaf_index: 2,
        merkle_proof: [SIBLING],
      }),
    );

    expect(screen.getByText("Batch · leaf 2")).toBeTruthy();
  });

  it("presents the proof as a claim, not as a verified result", async () => {
    await renderWith(
      makeDataset({
        batch_id: "batch-1",
        merkle_root: ROOT,
        leaf_index: 2,
        merkle_proof: [SIBLING],
      }),
    );

    // Nothing has checked the proof on this page, so it must not be graded.
    expect(screen.queryByText("Not verified")).toBeNull();
    expect(screen.queryByText("Verified on-chain")).toBeNull();
  });

  it("labels the transaction as the batch's anchor transaction", async () => {
    await renderWith(
      makeDataset({
        batch_id: "batch-1",
        merkle_root: ROOT,
        leaf_index: 2,
        merkle_proof: [SIBLING],
      }),
    );

    expect(screen.getByText("Batch Transaction")).toBeTruthy();
    expect(screen.queryByText("Transaction")).toBeNull();
  });

  it("links to the verify page with the dataset hash prefilled", async () => {
    await renderWith(
      makeDataset({
        batch_id: "batch-1",
        merkle_root: ROOT,
        leaf_index: 2,
        merkle_proof: [SIBLING],
      }),
    );

    const recheck = screen.getByRole("link", {
      name: /Re-check this inclusion proof/,
    });
    expect(recheck.getAttribute("href")).toBe(`/verify?dataset_hash=${HASH}`);
  });

  it("still offers verification for a batch that is not anchored yet", async () => {
    await renderWith(
      makeDataset({
        status: "pending",
        stellar_tx_hash: undefined,
        batch_id: "batch-1",
        merkle_root: ROOT,
        leaf_index: 0,
        merkle_proof: [],
      }),
    );

    const verify = screen.getByRole("link", { name: "Verify On-Chain" });
    expect(verify.getAttribute("href")).toBe(`/verify?dataset_hash=${HASH}`);
  });

  it("explains an empty sibling path for a single-leaf batch", async () => {
    await renderWith(
      makeDataset({
        batch_id: "batch-1",
        merkle_root: ROOT,
        leaf_index: 0,
        merkle_proof: [],
      }),
    );

    expect(screen.getByText(/this batch has a single leaf/)).toBeTruthy();
  });
});
