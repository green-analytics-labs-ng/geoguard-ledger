import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import MerkleProof, {
  InclusionVerdictBadge,
  ProofPath,
} from "../../src/components/MerkleProof";

const ROOT = "a".repeat(64);
const SIBLING_1 = "b".repeat(64);
const SIBLING_2 = "c".repeat(64);

describe("ProofPath", () => {
  it("lists every sibling hash bottom-up, numbered from one", () => {
    render(<ProofPath siblings={[SIBLING_1, SIBLING_2]} />);

    expect(screen.getByText(SIBLING_1)).toBeTruthy();
    expect(screen.getByText(SIBLING_2)).toBeTruthy();
    expect(screen.getByText("1")).toBeTruthy();
    expect(screen.getByText("2")).toBeTruthy();
  });

  it("explains that an empty path means a single-leaf batch", () => {
    render(<ProofPath siblings={[]} />);

    expect(screen.getByText(/this batch has a single leaf/i)).toBeTruthy();
    expect(screen.queryByRole("listitem")).toBeNull();
  });
});

describe("InclusionVerdictBadge", () => {
  it("shows an on-chain verdict", () => {
    render(<InclusionVerdictBadge verifiedLocally verifiedOnChain />);

    expect(screen.getByText("Verified on-chain")).toBeTruthy();
  });

  it("shows a local-only verdict when the on-chain check is unavailable", () => {
    render(<InclusionVerdictBadge verifiedLocally verifiedOnChain={null} />);

    expect(
      screen.getByText(/Verified locally — on-chain check unavailable/),
    ).toBeTruthy();
  });

  it("shows not verified when the proof did not check out", () => {
    render(
      <InclusionVerdictBadge verifiedLocally={false} verifiedOnChain={false} />,
    );

    expect(screen.getByText("Not verified")).toBeTruthy();
  });
});

describe("MerkleProof", () => {
  it("shows the root, leaf position and proof length", () => {
    render(
      <MerkleProof
        root={ROOT}
        leafIndex={3}
        proof={[SIBLING_1, SIBLING_2]}
        verifiedLocally
        verifiedOnChain
      />,
    );

    expect(screen.getByText("Merkle Inclusion Proof")).toBeTruthy();
    expect(screen.getByText(ROOT)).toBeTruthy();
    expect(screen.getByText("3")).toBeTruthy();
    expect(screen.getByText("2 siblings")).toBeTruthy();
    expect(screen.getByText(SIBLING_1)).toBeTruthy();
    expect(screen.getByText(SIBLING_2)).toBeTruthy();
  });

  it("uses the singular for a one-sibling proof", () => {
    render(
      <MerkleProof
        root={ROOT}
        leafIndex={0}
        proof={[SIBLING_1]}
        verifiedLocally
        verifiedOnChain={null}
      />,
    );

    expect(screen.getByText("1 sibling")).toBeTruthy();
  });

  it("carries the batch id when one is supplied", () => {
    render(
      <MerkleProof
        root={ROOT}
        leafIndex={0}
        proof={[]}
        batchId="11111111-2222-3333-4444-555555555555"
        verifiedLocally
        verifiedOnChain
      />,
    );

    expect(
      screen.getByText("11111111-2222-3333-4444-555555555555"),
    ).toBeTruthy();
  });

  it("omits the batch row when no batch id is supplied", () => {
    render(
      <MerkleProof
        root={ROOT}
        leafIndex={0}
        proof={[]}
        verifiedLocally
        verifiedOnChain
      />,
    );

    expect(screen.queryByText("Batch")).toBeNull();
  });

  it("surfaces a failed proof", () => {
    render(
      <MerkleProof
        root={ROOT}
        leafIndex={0}
        proof={[SIBLING_1]}
        verifiedLocally={false}
        verifiedOnChain={false}
      />,
    );

    expect(screen.getByText("Not verified")).toBeTruthy();
  });

  it("shows the proof material without grading it when showVerdict is off", () => {
    render(
      <MerkleProof
        root={ROOT}
        leafIndex={1}
        proof={[SIBLING_1]}
        showVerdict={false}
      />,
    );

    expect(screen.getByText(ROOT)).toBeTruthy();
    expect(screen.getByText(SIBLING_1)).toBeTruthy();
    // An ungraded proof must not be labelled as failed.
    expect(screen.queryByText("Not verified")).toBeNull();
    expect(screen.queryByText(/Verified locally/)).toBeNull();
  });
});
