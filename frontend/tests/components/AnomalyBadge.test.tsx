import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import AnomalyBadge from "../../src/components/AnomalyBadge";

function badge(): HTMLElement {
  return screen.getByTitle(/Anomaly score/);
}

describe("AnomalyBadge", () => {
  it("renders the green Normal tier below 5%", () => {
    render(<AnomalyBadge score={0.02} />);

    expect(badge().textContent).toContain("2.0%");
    expect(badge().textContent).toContain("Normal");
    expect(badge().className).toContain("bg-green-100");
  });

  it("renders the yellow Suspect tier between 5% and 20%", () => {
    render(<AnomalyBadge score={0.12} />);

    expect(badge().textContent).toContain("12.0%");
    expect(badge().textContent).toContain("Suspect");
    expect(badge().className).toContain("bg-yellow-100");
  });

  it("renders the red Anomalous tier at 20% and above", () => {
    render(<AnomalyBadge score={0.35} />);

    expect(badge().textContent).toContain("35.0%");
    expect(badge().textContent).toContain("Anomalous");
    expect(badge().className).toContain("bg-red-100");
  });

  it("treats the 5% boundary as Suspect", () => {
    render(<AnomalyBadge score={0.05} />);
    expect(badge().textContent).toContain("Suspect");
  });

  it("treats the 20% boundary as Anomalous", () => {
    render(<AnomalyBadge score={0.2} />);
    expect(badge().textContent).toContain("Anomalous");
  });

  it("treats a clean dataset (0%) as Normal", () => {
    render(<AnomalyBadge score={0} />);
    expect(badge().textContent).toContain("0.0%");
    expect(badge().textContent).toContain("Normal");
  });

  it("hides the label when showLabel is false", () => {
    render(<AnomalyBadge score={0.02} showLabel={false} />);

    expect(badge().textContent).toContain("2.0%");
    expect(badge().textContent).not.toContain("Normal");
  });

  it("exposes the score and tier in the title attribute", () => {
    render(<AnomalyBadge score={0.25} />);
    expect(badge().getAttribute("title")).toBe("Anomaly score: 25.0% - Anomalous");
  });

  it("supports the md size", () => {
    render(<AnomalyBadge score={0.02} size="md" />);
    expect(badge().className).toContain("px-3");
  });

  it("defaults to the sm size", () => {
    render(<AnomalyBadge score={0.02} />);
    expect(badge().className).toContain("px-2");
  });
});
