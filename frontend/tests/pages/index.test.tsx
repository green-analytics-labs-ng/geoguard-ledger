import { describe, it, expect } from "vitest";
import { DashboardPage } from "../../src/pages";

describe("Page exports", () => {
  it("DashboardPage is exported", () => {
    expect(DashboardPage).toBeDefined();
  });
});
