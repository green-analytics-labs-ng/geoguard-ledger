import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import DatasetTable from "../../src/components/DatasetTable";
import type { DatasetResponse } from "../../src/types";

const HASH = "a".repeat(64);
const TX_HASH = "b".repeat(64);

function makeDataset(overrides: Partial<DatasetResponse> = {}): DatasetResponse {
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
    renderTable({ datasets: [], loading: false, error: "Soroban RPC unreachable" });

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

    expect(screen.getByText("—")).toBeTruthy();
  });

  it("renders an explorer link when a transaction hash exists", () => {
    renderTable({ datasets: [makeDataset()], loading: false, error: null });

    const explorer = screen.getByRole("link", {
      name: `${TX_HASH.slice(0, 8)}...${TX_HASH.slice(-8)}`,
    });
    expect(explorer.getAttribute("href")).toContain(`/tx/${TX_HASH}`);
  });
});
