import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import SubmissionStepper from "../../src/components/SubmissionStepper";
import type { SubmissionStep } from "../../src/types";

const LABELS = ["Upload", "Preview", "AI Report", "Sign", "Confirmed"];

function completedCount(container: HTMLElement): number {
  // Each completed step renders a check icon inside its circle.
  return container.querySelectorAll("svg").length;
}

describe("SubmissionStepper", () => {
  it("renders every step label", () => {
    render(<SubmissionStepper currentStep="upload" />);

    for (const label of LABELS) {
      expect(screen.getByText(label)).toBeTruthy();
    }
  });

  it("shows the index of each step while none are completed", () => {
    const { container } = render(<SubmissionStepper currentStep="upload" />);

    expect(completedCount(container)).toBe(0);
    for (const index of ["1", "2", "3", "4", "5"]) {
      expect(screen.getByText(index)).toBeTruthy();
    }
  });

  it("marks earlier steps as completed and keeps later indices", () => {
    const { container } = render(<SubmissionStepper currentStep="ai-report" />);

    expect(completedCount(container)).toBe(2);
    for (const index of ["3", "4", "5"]) {
      expect(screen.getByText(index)).toBeTruthy();
    }
  });

  it("does not mark the current step as completed", () => {
    const { container } = render(<SubmissionStepper currentStep="sign" />);

    expect(completedCount(container)).toBe(3);
    expect(screen.getByText("4")).toBeTruthy();
  });

  it("marks all but the final step as completed at the end", () => {
    const { container } = render(<SubmissionStepper currentStep="confirmed" />);

    expect(completedCount(container)).toBe(4);
    expect(screen.getByText("5")).toBeTruthy();
  });

  it("renders every step state without crashing", () => {
    const steps: SubmissionStep[] = [
      "upload",
      "preview",
      "ai-report",
      "sign",
      "confirmed",
    ];

    for (const step of steps) {
      const { container, unmount } = render(<SubmissionStepper currentStep={step} />);
      expect(container.textContent).toContain("Confirmed");
      unmount();
    }
  });
});
