/**
 * Issue #15: without an error boundary, a render error in any page took the
 * whole app down to a blank white screen. This asserts that a throwing route
 * is contained by the boundary mounted in `App.tsx`.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const freighter = vi.hoisted(() => ({
  isAllowed: vi.fn(),
  isConnected: vi.fn(),
  getAddress: vi.fn(),
  getNetwork: vi.fn(),
  signTransaction: vi.fn(),
  requestAccess: vi.fn(),
}));

vi.mock("@stellar/freighter-api", () => freighter);

// The dashboard route throws during render.
vi.mock("../../src/pages/DashboardPage", () => ({
  default: function Boom(): never {
    throw new Error("kaboom");
  },
}));

import App from "../../src/App";

describe("App error boundary", () => {
  it("shows a recoverable fallback instead of a blank screen", () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    freighter.isAllowed.mockResolvedValue({ isAllowed: false });

    window.history.pushState({}, "", "/");
    render(<App />);

    expect(screen.getByRole("alert")).toBeTruthy();
    expect(screen.getByText("Something went wrong")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();

    consoleError.mockRestore();
  });
});
