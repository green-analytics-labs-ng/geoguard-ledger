import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import AnomalyWarnings from "../../src/components/AnomalyWarnings";

const ERROR_FINDING = "[ERROR] pH: 1 value(s) outside the plausible range 0 to 14 (rows 4)";
const WARNING_FINDING =
  "[WARNING] temperature: 1 value(s) outside the plausible range -10 to 50 C (rows 6)";

function rootClassOf(container: HTMLElement): string {
  const root = container.firstElementChild;
  if (!root) throw new Error("expected AnomalyWarnings to render a root element");
  return root.className;
}

describe("AnomalyWarnings", () => {
  it("renders nothing when there are no findings", () => {
    const { container } = render(<AnomalyWarnings warnings={[]} />);
    expect(container.textContent).toBe("");
  });

  it("lists every finding verbatim", () => {
    render(<AnomalyWarnings warnings={[ERROR_FINDING, WARNING_FINDING]} />);

    expect(screen.getByText(ERROR_FINDING)).toBeTruthy();
    expect(screen.getByText(WARNING_FINDING)).toBeTruthy();
  });

  it("counts impossible values and uses error styling", () => {
    const { container } = render(
      <AnomalyWarnings warnings={[ERROR_FINDING, WARNING_FINDING]} />,
    );

    expect(screen.getByText("1 impossible value detected")).toBeTruthy();
    expect(rootClassOf(container)).toContain("bg-red-50");
  });

  it("uses singular wording for exactly one error", () => {
    render(<AnomalyWarnings warnings={[ERROR_FINDING]} />);
    expect(screen.getByText("1 impossible value detected")).toBeTruthy();
  });

  it("uses plural wording for multiple errors", () => {
    const second = "[ERROR] conductivity: 1 value(s) negative (rows 3)";
    const { container } = render(<AnomalyWarnings warnings={[ERROR_FINDING, second]} />);

    expect(screen.getByText("2 impossible values detected")).toBeTruthy();
    expect(rootClassOf(container)).toContain("bg-red-50");
  });

  it("uses warning styling when nothing is impossible", () => {
    const { container } = render(<AnomalyWarnings warnings={[WARNING_FINDING]} />);

    expect(screen.getByText("Plausibility warnings")).toBeTruthy();
    expect(rootClassOf(container)).toContain("bg-yellow-50");
  });
});
