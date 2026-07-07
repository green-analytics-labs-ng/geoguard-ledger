import { describe, it, expect } from "vitest";
import {
  AnomalyBadge,
  CsvDropzone,
  DatasetTable,
  SubmissionStepper,
  TxExplorerLink,
  VerificationResult,
  WalletConnector,
} from "../../src/components";

describe("Component exports", () => {
  it("AnomalyBadge is exported", () => {
    expect(AnomalyBadge).toBeDefined();
  });

  it("CsvDropzone is exported", () => {
    expect(CsvDropzone).toBeDefined();
  });

  it("DatasetTable is exported", () => {
    expect(DatasetTable).toBeDefined();
  });

  it("SubmissionStepper is exported", () => {
    expect(SubmissionStepper).toBeDefined();
  });

  it("TxExplorerLink is exported", () => {
    expect(TxExplorerLink).toBeDefined();
  });

  it("VerificationResult is exported", () => {
    expect(VerificationResult).toBeDefined();
  });

  it("WalletConnector is exported", () => {
    expect(WalletConnector).toBeDefined();
  });
});
