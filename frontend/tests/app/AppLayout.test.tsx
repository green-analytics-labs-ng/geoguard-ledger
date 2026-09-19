/**
 * The shared shell, through the real route table.
 *
 * Every page used to draw its own `<nav>`, so the page you were on decided how
 * many navigations existed and which one was marked. These tests render the
 * application at each route and assert there is one navigation, that it marks
 * exactly the section you are in, and that the pages no longer add their own.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";

const freighter = vi.hoisted(() => ({
  isAllowed: vi.fn(),
  isConnected: vi.fn(),
  getAddress: vi.fn(),
  getNetwork: vi.fn(),
  signTransaction: vi.fn(),
  requestAccess: vi.fn(),
}));

vi.mock("@stellar/freighter-api", () => freighter);

// The pages fetch on mount; the shell's structure is what is under test, so the
// API is stubbed rather than reached.
const datasetsApi = vi.hoisted(() => ({
  listDatasets: vi.fn(),
  getDataset: vi.fn(),
  uploadCsv: vi.fn(),
  anchorDataset: vi.fn(),
  submitDataset: vi.fn(),
}));

vi.mock("../../src/api/datasets", () => datasetsApi);

import App from "../../src/App";

/** Each route, the heading that proves it rendered, and the link it should mark. */
const ROUTES = [
  { path: "/", heading: "Dashboard", active: "Dashboard" },
  { path: "/upload", heading: "Upload Dataset", active: "Upload" },
  { path: "/datasets", heading: "Datasets", active: "Datasets" },
  // A dataset's own page is inside the Datasets section, not a section of its
  // own, so Datasets stays marked.
  { path: "/datasets/ds-1", heading: "Dataset Details", active: "Datasets" },
  { path: "/verify", heading: "Verify Dataset", active: "Verify" },
  { path: "/settings", heading: "Settings", active: "Settings" },
];

const SECTIONS = ["Dashboard", "Upload", "Datasets", "Verify", "Settings"];

beforeEach(() => {
  vi.clearAllMocks();
  freighter.isAllowed.mockResolvedValue({ isAllowed: false });
  freighter.isConnected.mockResolvedValue({ isConnected: false });
  freighter.getAddress.mockResolvedValue({ address: "" });
  freighter.getNetwork.mockResolvedValue({
    network: "TESTNET",
    networkPassphrase: "Test SDF Network ; September 2015",
  });
  datasetsApi.listDatasets.mockResolvedValue({ datasets: [], total: 0 });
  datasetsApi.getDataset.mockResolvedValue({
    dataset_id: "ds-1",
    dataset_hash: "a".repeat(64),
    status: "anchored",
    anomaly_score: 0.1,
    created_at: "2026-09-12T00:00:00Z",
  });
});

describe("AppLayout", () => {
  it.each(ROUTES)("marks only $active as current at $path", async ({ path, heading, active }) => {
    window.history.pushState({}, "", path);
    render(<App />);

    expect(await screen.findByRole("heading", { name: heading })).toBeTruthy();

    // One navigation, five sections: the page did not add a second one.
    const nav = screen.getByRole("navigation", { name: "Main" });
    const links = within(nav).getAllByRole("link");
    expect(links.map((link) => link.textContent)).toEqual(SECTIONS);

    const current = links.filter((link) => link.getAttribute("aria-current") === "page");
    expect(current.map((link) => link.textContent)).toEqual([active]);
  });

  it("links the brand back to the dashboard", async () => {
    window.history.pushState({}, "", "/settings");
    render(<App />);

    await screen.findByRole("heading", { name: "Settings" });

    const brand = screen.getByRole("link", { name: "GeoGuard Ledger" });
    expect(brand.getAttribute("href")).toBe("/");
    // The brand is not a section link, so it is not marked as the current one.
    expect(brand.getAttribute("aria-current")).toBeNull();
  });

  it("keeps the header while a route's chunk loads", async () => {
    window.history.pushState({}, "", "/");
    render(<App />);

    // The route is lazy, so the shell is on screen first and the page arrives
    // inside it — the header is never unmounted for a chunk fetch.
    expect(await screen.findByRole("navigation", { name: "Main" })).toBeTruthy();
    expect(await screen.findByRole("heading", { name: "Dashboard" })).toBeTruthy();
    expect(screen.getAllByRole("navigation")).toHaveLength(1);
  });
});
