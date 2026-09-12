import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import BatchBadge from "../../src/components/BatchBadge";

const ROOT = "f".repeat(64);

function renderBadge(leafIndex: number) {
  return render(
    <BatchBadge
      membership={{
        batchId: "batch-1",
        root: ROOT,
        leafIndex,
        proof: ["c".repeat(64)],
      }}
    />,
  );
}

describe("BatchBadge", () => {
  it("shows which leaf of the batch the dataset occupies", () => {
    renderBadge(3);

    expect(screen.getByText("Batch · leaf 3")).toBeTruthy();
  });

  it("names the root and batch so the claim can be inspected in place", () => {
    renderBadge(0);

    const title = screen.getByText("Batch · leaf 0").getAttribute("title");

    expect(title).toContain(ROOT);
    expect(title).toContain("batch-1");
  });

  it("renders a first-leaf position", () => {
    renderBadge(0);

    expect(screen.getByText("Batch · leaf 0")).toBeTruthy();
  });
});
