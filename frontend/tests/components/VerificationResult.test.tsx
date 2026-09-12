import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import VerificationResult, {
  VerificationResultEmpty,
} from "../../src/components/VerificationResult";
import type { InclusionProof, VerifyResult } from "../../src/types";

const HASH = "a".repeat(64);
const ROOT = "b".repeat(64);
const SIBLING = "c".repeat(64);

const ON_CHAIN_RECORD = {
  dataset_hash: HASH,
  anomaly_score: 1200,
  model_version: "isoforest_v1",
  timestamp: 1751715300,
  submitter: "GABCDEF",
};

function inclusion(overrides: Partial<InclusionProof> = {}): InclusionProof {
  return {
    root: ROOT,
    leaf_index: 2,
    proof: [SIBLING],
    batch_id: "batch-1",
    verified_locally: true,
    verified_on_chain: true,
    ...overrides,
  };
}

function result(overrides: Partial<VerifyResult> = {}): VerifyResult {
  return {
    match: false,
    on_chain_record: null,
    local_record: null,
    ...overrides,
  };
}

describe("VerificationResult", () => {
  it("confirms an individually anchored dataset", () => {
    render(
      <VerificationResult
        result={result({ match: true, on_chain_record: ON_CHAIN_RECORD })}
      />,
    );

    expect(screen.getByText("Dataset Verified")).toBeTruthy();
    expect(screen.getByText("On-Chain Record")).toBeTruthy();
  });

  it("reports an unverified hash with no inclusion proof", () => {
    render(<VerificationResult result={result()} />);

    expect(screen.getByText("Not Verified")).toBeTruthy();
    expect(
      screen.getByText(/was not found on the Stellar blockchain/),
    ).toBeTruthy();
  });

  it("treats a verified inclusion proof as verified without a standalone record", () => {
    render(<VerificationResult result={result({ inclusion: inclusion() })} />);

    expect(screen.getByText("Included in Anchored Batch")).toBeTruthy();
    expect(
      screen.getByText(/Merkle inclusion proof against an anchored batch root/),
    ).toBeTruthy();
    // The proof itself is shown so a third party can re-check it.
    expect(screen.getByText("Merkle Inclusion Proof")).toBeTruthy();
    expect(screen.getByText(ROOT)).toBeTruthy();
    expect(screen.getByText(SIBLING)).toBeTruthy();
    expect(screen.getByText("Verified on-chain")).toBeTruthy();
  });

  it("does not treat an on-chain rejected proof as verified", () => {
    render(
      <VerificationResult
        result={result({
          inclusion: inclusion({ verified_on_chain: false }),
        })}
      />,
    );

    expect(screen.getByText("Not Verified")).toBeTruthy();
    expect(screen.getByText("Not verified")).toBeTruthy();
    expect(screen.getByText(/batch root is not anchored yet/)).toBeTruthy();
  });

  it("accepts a local-only verification when on-chain is unavailable", () => {
    render(
      <VerificationResult
        result={result({
          inclusion: inclusion({ verified_on_chain: null }),
        })}
      />,
    );

    expect(screen.getByText("Included in Anchored Batch")).toBeTruthy();
    expect(
      screen.getByText(/Verified locally — on-chain check unavailable/),
    ).toBeTruthy();
  });

  it("ignores a null inclusion block", () => {
    render(<VerificationResult result={result({ inclusion: null })} />);

    expect(screen.getByText("Not Verified")).toBeTruthy();
    expect(screen.queryByText("Merkle Inclusion Proof")).toBeNull();
  });

  it("shows the re-computed hash for file uploads", () => {
    render(<VerificationResult result={result({ re_computed_hash: HASH })} />);

    expect(screen.getByText("Re-computed Hash")).toBeTruthy();
    expect(screen.getByText(HASH)).toBeTruthy();
  });
});

describe("VerificationResultEmpty", () => {
  it("prompts for input before a check is run", () => {
    render(<VerificationResultEmpty />);

    expect(screen.getByText(/Upload a data file or paste a hash/)).toBeTruthy();
  });

  it("is inert", () => {
    render(<VerificationResultEmpty />);

    fireEvent.click(screen.getByText(/Upload a data file or paste a hash/));

    expect(screen.queryByText("Dataset Verified")).toBeNull();
  });
});
