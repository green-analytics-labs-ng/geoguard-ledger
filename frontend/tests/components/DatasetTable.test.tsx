import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import DatasetTable from "../../src/components/DatasetTable";
import type { DatasetResponse } from "../../src/types";

const HASH = "a".repeat(64);
const TX_HASH = "b".repeat(64);
const ROOT = "f".repeat(64);
const SIBLING = "c".repeat(64);

function makeDataset(
  overrides: Partial<DatasetResponse> = {},
): DatasetResponse {
  return {
    dataset_id: "11111111-2222-3333-4444-555555555555",
    dataset_hash: HASH,
    status: "anchored",
    anomaly_score: 0.12,
    created_at: "2026-07-05T12:00:00Z",
    stellar_tx_hash: TX_HASH,
    ...overrides,
  };
}

interface Props {
  datasets: DatasetResponse[];
  loading: boolean;
  error: string | null;
}

function renderTable(props: Props) {
  return render(
    <MemoryRouter>
      <DatasetTable {...props} />
    </MemoryRouter>,
  );
}

describe("DatasetTable", () => {
  it("shows a loading state instead of the table", () => {
    renderTable({ datasets: [], loading: true, error: null });

    expect(screen.getByText("Loading datasets...")).toBeTruthy();
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("shows the error message when one is provided", () => {
    renderTable({
      datasets: [],
      loading: false,
      error: "Soroban RPC unreachable",
    });

    expect(screen.getByText("Soroban RPC unreachable")).toBeTruthy();
  });

  it("prefers the error over the empty state", () => {
    renderTable({ datasets: [], loading: false, error: "boom" });

    expect(screen.getByText("boom")).toBeTruthy();
    expect(screen.queryByText("No datasets anchored yet.")).toBeNull();
  });

  it("shows an empty state with a call to action", () => {
    renderTable({ datasets: [], loading: false, error: null });

    expect(screen.getByText("No datasets anchored yet.")).toBeTruthy();
    const cta = screen.getByRole("link", { name: "Upload your first dataset" });
    expect(cta.getAttribute("href")).toBe("/upload");
  });

  it("renders a populated dataset row", () => {
    renderTable({ datasets: [makeDataset()], loading: false, error: null });

    expect(screen.getByRole("table")).toBeTruthy();
    expect(screen.getByText("Anchored")).toBeTruthy();
    expect(screen.getByText(`${HASH.slice(0, 12)}...`)).toBeTruthy();
    expect(screen.getByText("12.0%")).toBeTruthy();
  });

  it("links the dataset id to its detail page", () => {
    const dataset = makeDataset();
    renderTable({ datasets: [dataset], loading: false, error: null });

    const link = screen.getByRole("link", { name: "11111111..." });
    expect(link.getAttribute("href")).toBe(`/datasets/${dataset.dataset_id}`);
  });

  it("renders pending, anchored and failed statuses", () => {
    renderTable({
      datasets: [
        makeDataset({ dataset_id: "pending-1", status: "pending" }),
        makeDataset({ dataset_id: "failed-1", status: "failed" }),
      ],
      loading: false,
      error: null,
    });

    expect(screen.getByText("Pending")).toBeTruthy();
    expect(screen.getByText("Failed")).toBeTruthy();
  });

  it("shows a placeholder when a dataset has no transaction hash", () => {
    renderTable({
      datasets: [makeDataset({ stellar_tx_hash: undefined })],
      loading: false,
      error: null,
    });

    // Scope to the last cell: the batch column also uses a dash placeholder.
    const row = screen.getByRole("row", { name: /11111111/ });
    const cells = within(row).getAllByRole("cell");
    expect(within(cells[cells.length - 1]).getByText("—")).toBeTruthy();
  });

  it("marks a batched dataset with its leaf position", () => {
    renderTable({
      datasets: [
        makeDataset({
          batch_id: "batch-1",
          merkle_root: ROOT,
          leaf_index: 3,
          merkle_proof: [SIBLING],
        }),
      ],
      loading: false,
      error: null,
    });

    expect(screen.getByText("Batch · leaf 3")).toBeTruthy();
  });

  it("names the batch root on the badge so it can be inspected in place", () => {
    renderTable({
      datasets: [
        makeDataset({
          batch_id: "batch-7",
          merkle_root: ROOT,
          leaf_index: 0,
          merkle_proof: [],
        }),
      ],
      loading: false,
      error: null,
    });

    const title = screen.getByText("Batch · leaf 0").getAttribute("title");
    expect(title).toContain(ROOT);
    expect(title).toContain("batch-7");
  });

  it("distinguishes batched from standalone datasets in one table", () => {
    renderTable({
      datasets: [
        makeDataset({
          dataset_id: "batched-1",
          batch_id: "batch-1",
          merkle_root: ROOT,
          leaf_index: 1,
          merkle_proof: [SIBLING],
        }),
        makeDataset({ dataset_id: "standalone-1" }),
      ],
      loading: false,
      error: null,
    });

    expect(screen.getByText("Batch · leaf 1")).toBeTruthy();
    // Only the standalone row falls back to the dash in the batch column.
    expect(screen.getAllByText("—")).toHaveLength(1);
  });

  it("renders an explorer link when a transaction hash exists", () => {
    renderTable({ datasets: [makeDataset()], loading: false, error: null });

    const explorer = screen.getByRole("link", {
      name: `${TX_HASH.slice(0, 8)}...${TX_HASH.slice(-8)}`,
    });
    expect(explorer.getAttribute("href")).toContain(`/tx/${TX_HASH}`);
  });
});
