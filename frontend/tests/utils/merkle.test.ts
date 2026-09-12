import { describe, it, expect } from "vitest";
import { inclusionVerdict, isInclusionVerified } from "../../src/utils/merkle";

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
