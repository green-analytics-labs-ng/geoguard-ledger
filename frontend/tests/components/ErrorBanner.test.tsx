import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import ErrorBanner from "../../src/components/ErrorBanner";

describe("ErrorBanner", () => {
  it("renders the message as an alert", () => {
    render(<ErrorBanner message="Something went wrong" />);

    expect(screen.getByRole("alert").textContent).toBe("Something went wrong");
  });

  it("turns a URL in the message into a link", () => {
    render(
      <ErrorBanner message="Fund it at https://friendbot.stellar.org?addr=GABC then retry." />,
    );

    const link = screen.getByRole("link");
    expect(link.getAttribute("href")).toBe("https://friendbot.stellar.org?addr=GABC");
    expect(link.textContent).toBe("https://friendbot.stellar.org?addr=GABC");
  });

  it("opens the link in a new tab without leaking the referrer", () => {
    render(<ErrorBanner message="See https://example.com/x" />);

    const link = screen.getByRole("link");
    expect(link.getAttribute("target")).toBe("_blank");
    expect(link.getAttribute("rel")).toBe("noreferrer");
  });

  it("keeps the surrounding text alongside the link", () => {
    render(<ErrorBanner message="Fund it at https://example.com/x now." />);

    expect(screen.getByRole("alert").textContent).toBe("Fund it at https://example.com/x now.");
  });

  it("renders no link when the message has no URL", () => {
    render(<ErrorBanner message="No link here" />);

    expect(screen.queryByRole("link")).toBeNull();
  });

  it("appends the caller's className for layout", () => {
    render(<ErrorBanner message="Oops" className="mb-6" />);

    const alert = screen.getByRole("alert");
    expect(alert.className).toContain("mb-6");
    expect(alert.className).toContain("bg-red-50");
  });
});
