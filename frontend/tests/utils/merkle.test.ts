import { describe, it, expect } from "vitest";
import {
  batchMembership,
  inclusionVerdict,
  isInclusionVerified,
} from "../../src/utils/merkle";

const ROOT = "f".repeat(64);

describe("inclusionVerdict", () => {
  it("prefers a positive on-chain verdict", () => {
    expect(inclusionVerdict(true, true)).toBe("on-chain");
    expect(inclusionVerdict(false, true)).toBe("on-chain");
  });

  it("treats an explicit on-chain rejection as authoritative", () => {
    // The contract said no, so a local pass must not override it.
    expect(inclusionVerdict(true, false)).toBe("unverified");
    expect(inclusionVerdict(undefined, false)).toBe("unverified");
  });

  it("falls back to a local pass when the on-chain check is unavailable", () => {
    expect(inclusionVerdict(true, null)).toBe("local");
    expect(inclusionVerdict(true, undefined)).toBe("local");
  });

  it("reports unverified when no check passed", () => {
    expect(inclusionVerdict(false, null)).toBe("unverified");
    expect(inclusionVerdict(undefined, null)).toBe("unverified");
  });
});

describe("isInclusionVerified", () => {
  it("accepts on-chain and local verdicts", () => {
    expect(isInclusionVerified("on-chain")).toBe(true);
    expect(isInclusionVerified("local")).toBe(true);
  });

  it("rejects unverified", () => {
    expect(isInclusionVerified("unverified")).toBe(false);
  });
});

describe("batchMembership", () => {
  it("describes a dataset committed to by a batch root", () => {
    const proof = ["a".repeat(64), "b".repeat(64)];

    expect(
      batchMembership({
        batch_id: "batch-1",
        merkle_root: ROOT,
        leaf_index: 2,
        merkle_proof: proof,
      }),
    ).toEqual({
      batchId: "batch-1",
      root: ROOT,
      leafIndex: 2,
      proof,
    });
  });

  it("keeps an empty proof path, which a single-leaf batch legitimately has", () => {
    const membership = batchMembership({
      batch_id: "batch-1",
      merkle_root: ROOT,
      leaf_index: 0,
      merkle_proof: [],
    });

    expect(membership).not.toBeNull();
    expect(membership?.proof).toEqual([]);
  });

  it("reports no membership for a standalone dataset", () => {
    expect(
      batchMembership({
        batch_id: null,
        merkle_root: null,
        leaf_index: null,
        merkle_proof: null,
      }),
    ).toBeNull();
  });

  it("reports no membership when the batch fields are absent", () => {
    expect(batchMembership({})).toBeNull();
  });

  it("treats a proof that has not been recorded yet as an empty path", () => {
    // The dataset is already assigned to a root, so it is a member even though
    // its path is missing; the caller can still show the claim and re-check it.
    expect(
      batchMembership({
        batch_id: "batch-1",
        merkle_root: ROOT,
        leaf_index: 1,
      }),
    ).toEqual({ batchId: "batch-1", root: ROOT, leafIndex: 1, proof: [] });
  });
});
