/**
 * Accessibility smoke tests, one per route.
 *
 * The review that drove the a11y work counted six `aria`/`role` attributes in
 * all of `src` and two `<label>` elements, so the fixes it prompted (labels,
 * the skip link, `role="status"` on progress, `role="alert"` on errors) were
 * each verified by hand or by a focused assertion. `vitest-axe` was installed
 * at the same time but never actually run, which left the whole app one
 * unlabelled control away from regressing unnoticed.
 *
 * Each case renders the real `App` — shell, navigation and page — because the
 * violations that matter most here are in the relationship between them: a
 * landmark that stops wrapping the content, a heading level that jumps, or a
 * page that loses its only `<h1>`. The API and wallet are mocked so the page
 * reaches its rendered state instead of a loading spinner.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { configureAxe } from "vitest-axe";

/**
 * axe, with the one rule jsdom cannot answer switched off.
 *
 * `color-contrast` needs computed styles and element geometry, and jsdom has no
 * layout engine: axe returns "incomplete" for every node and logs a canvas
 * error while trying. Leaving it on would mean a passing suite that never
 * actually checked contrast, so the rule is disabled here and contrast is
 * covered by review against the design tokens instead.
 */
const axe = configureAxe({
  rules: { "color-contrast": { enabled: false } },
});

const freighter = vi.hoisted(() => ({
  isAllowed: vi.fn(),
  isConnected: vi.fn(),
  getAddress: vi.fn(),
  getNetwork: vi.fn(),
  signTransaction: vi.fn(),
  requestAccess: vi.fn(),
}));

vi.mock("@stellar/freighter-api", () => freighter);

const datasetsApi = vi.hoisted(() => ({
  listDatasets: vi.fn(),
  getDataset: vi.fn(),
  uploadCsv: vi.fn(),
  anchorDataset: vi.fn(),
  submitDataset: vi.fn(),
}));

vi.mock("../../src/api/datasets", () => datasetsApi);

import App from "../../src/App";
import type { DatasetResponse } from "../../src/types";

const HASH = "a".repeat(64);
const TX_HASH = "b".repeat(64);

const DATASET: DatasetResponse = {
  dataset_id: "ds-1",
  dataset_hash: HASH,
  status: "anchored",
  anomaly_score: 0.12,
  stellar_tx_hash: TX_HASH,
  created_at: "2026-07-05T12:00:00Z",
};

/** Every client-side route, with the `<h1>` its page is expected to render. */
const ROUTES = [
  { path: "/", heading: "Dashboard" },
  { path: "/upload", heading: "Upload Dataset" },
  { path: "/datasets", heading: "Datasets" },
  { path: "/datasets/ds-1", heading: "Dataset Details" },
  { path: "/verify", heading: "Verify Dataset" },
  { path: "/settings", heading: "Settings" },
];

async function renderRoute(path: string, heading: string): Promise<HTMLElement> {
  window.history.pushState({}, "", path);
  const { container } = render(<App />);

  // Waiting for the page's own heading rather than the layout's: the route
  // chunks are lazy, so the shell renders before the page it hosts.
  expect(await screen.findByRole("heading", { name: heading })).toBeTruthy();
  return container;
}

describe.each(ROUTES)("$path", ({ path, heading }) => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();

    freighter.isAllowed.mockResolvedValue({ isAllowed: false });
    freighter.isConnected.mockResolvedValue({ isConnected: false });
    freighter.getAddress.mockResolvedValue({ address: "" });
    freighter.getNetwork.mockResolvedValue({
      network: "TESTNET",
      networkPassphrase: "Test SDF Network ; September 2015",
    });
    freighter.requestAccess.mockResolvedValue({});
    freighter.signTransaction.mockResolvedValue({ signedTxXdr: "" });

    datasetsApi.listDatasets.mockResolvedValue({ datasets: [], total: 0 });
    datasetsApi.getDataset.mockResolvedValue(DATASET);
  });

  it("has no detectable accessibility violations", async () => {
    const container = await renderRoute(path, heading);

    const results = await axe(container);

    expect(results).toHaveNoViolations();
  });
});
