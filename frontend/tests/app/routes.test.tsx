/**
 * Tests for the centralized route table.
 *
 * Issue #9: `routes.tsx` used to be a dead stub containing only a Vite
 * reference comment, with routes defined inline in `App.tsx`. The table now
 * lives in one place and is consumed by `App.tsx`, so these tests pin its
 * contents to catch silent additions, removals or duplicates.
 */

import { describe, it, expect } from "vitest";
import { isValidElement } from "react";
import { routes } from "../../src/routes";

const EXPECTED_PATHS = [
  "/",
  "/upload",
  "/datasets",
  "/datasets/:id",
  "/verify",
  "/settings",
];

describe("routes", () => {
  it("defines exactly the documented paths, in order", () => {
    expect(routes.map((route) => route.path)).toEqual(EXPECTED_PATHS);
  });

  it("contains no duplicate paths", () => {
    const paths = routes.map((route) => route.path);
    expect(new Set(paths).size).toBe(paths.length);
  });

  it("renders a React element for every route", () => {
    for (const route of routes) {
      expect(isValidElement(route.element)).toBe(true);
    }
  });

  it("uses absolute paths so nested routes resolve predictably", () => {
    for (const route of routes) {
      expect(route.path.startsWith("/")).toBe(true);
    }
  });

  it("uses a parameterized path for dataset details", () => {
    const detail = routes.find((route) => route.path === "/datasets/:id");
    expect(detail).toBeTruthy();
    expect(detail?.path).toContain(":id");
  });
});
