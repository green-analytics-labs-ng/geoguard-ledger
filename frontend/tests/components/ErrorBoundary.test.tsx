import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ErrorBoundary from "../../src/components/ErrorBoundary";

function Boom(): never {
  throw new Error("boom");
}

describe("ErrorBoundary", () => {
  it("renders its children when there is no error", () => {
    render(
      <ErrorBoundary>
        <div>all good</div>
      </ErrorBoundary>,
    );

    expect(screen.getByText("all good")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("renders a fallback with a retry action when a child throws", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );

    expect(screen.getByRole("alert")).toBeTruthy();
    expect(screen.getByText("Something went wrong")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();

    spy.mockRestore();
  });

  it("recovers and re-renders children when the retry action is clicked", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});

    let shouldThrow = true;
    function MaybeBoom(): string | React.JSX.Element {
      if (shouldThrow) throw new Error("boom");
      return <div>recovered</div>;
    }

    render(
      <ErrorBoundary>
        <MaybeBoom />
      </ErrorBoundary>,
    );
    expect(screen.getByRole("alert")).toBeTruthy();

    shouldThrow = false;
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(screen.getByText("recovered")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();

    spy.mockRestore();
  });

  it("keeps showing the fallback while the child still throws", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(screen.getByRole("alert")).toBeTruthy();
    expect(screen.getByText("Something went wrong")).toBeTruthy();

    spy.mockRestore();
  });

  it("logs the caught error for debugging", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );

    expect(spy).toHaveBeenCalled();
    const logged = spy.mock.calls.flat().join(" ");
    expect(logged).toContain("GeoGuard Ledger UI");

    spy.mockRestore();
  });
});
