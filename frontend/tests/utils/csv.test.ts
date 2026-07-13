import { describe, it, expect } from "vitest";
import {
  isSupportedFormat,
  validateDataFile,
  validateCsvFile,
  parseCsvPreview,
  parseJsonPreview,
  type CsvPreview,
} from "../../src/utils/csv";

// ── isSupportedFormat ────────────────────────────────────────────

describe("isSupportedFormat", () => {
  it("accepts .csv", () => {
    expect(isSupportedFormat("data.csv")).toBe(true);
  });

  it("accepts .json", () => {
    expect(isSupportedFormat("data.json")).toBe(true);
  });

  it("is case-insensitive for uppercase .CSV", () => {
    expect(isSupportedFormat("DATA.CSV")).toBe(true);
  });

  it("is case-insensitive for uppercase .JSON", () => {
    expect(isSupportedFormat("DATA.JSON")).toBe(true);
  });

  it("is case-insensitive for mixed case", () => {
    expect(isSupportedFormat("Data.JsOn")).toBe(true);
  });

  it("rejects .txt", () => {
    expect(isSupportedFormat("data.txt")).toBe(false);
  });

  it("rejects .xml", () => {
    expect(isSupportedFormat("data.xml")).toBe(false);
  });

  it("rejects no extension", () => {
    expect(isSupportedFormat("data")).toBe(false);
  });

  it("rejects empty string", () => {
    expect(isSupportedFormat("")).toBe(false);
  });

  it("rejects double extension .csv.bak", () => {
    expect(isSupportedFormat("data.csv.bak")).toBe(false);
  });

  it("accepts filename with path separators", () => {
    expect(isSupportedFormat("path/to/file.json")).toBe(true);
  });
});

// ── validateDataFile ─────────────────────────────────────────────

describe("validateDataFile", () => {
  it("accepts a valid .csv File", () => {
    const file = new File(["col1,col2\n1,2\n"], "data.csv", { type: "text/csv" });
    expect(validateDataFile(file)).toBeNull();
  });

  it("accepts a valid .json File", () => {
    const file = new File(['[{"a":1}]'], "data.json", { type: "application/json" });
    expect(validateDataFile(file)).toBeNull();
  });

  it("rejects unsupported extension", () => {
    const file = new File(["hello"], "data.txt", { type: "text/plain" });
    expect(validateDataFile(file)).toBe("File must be a .csv or .json");
  });

  it("rejects empty file", () => {
    const file = new File([], "data.csv", { type: "text/csv" });
    // new File([]) has size 0
    expect(validateDataFile(file)).toBe("File is empty");
  });

  it("rejects file with no extension", () => {
    const file = new File(["data"], "data", { type: "application/octet-stream" });
    expect(validateDataFile(file)).toBe("File must be a .csv or .json");
  });
});

// ── validateCsvFile (deprecated alias) ────────────────────────────

describe("validateCsvFile", () => {
  it("delegates to validateDataFile (accepts .json too)", () => {
    const file = new File(['[{"a":1}]'], "data.json", { type: "application/json" });
    expect(validateCsvFile(file)).toBeNull();
  });

  it("rejects unsupported extensions same as validateDataFile", () => {
    const file = new File(["hello"], "data.txt", { type: "text/plain" });
    expect(validateCsvFile(file)).toBe("File must be a .csv or .json");
  });
});

// ── parseCsvPreview ──────────────────────────────────────────────

describe("parseCsvPreview", () => {
  it("parses a simple CSV", () => {
    const result = parseCsvPreview("a,b\n1,2\n3,4\n");
    expect(result.headers).toEqual(["a", "b"]);
    expect(result.rows).toEqual([["1", "2"], ["3", "4"]]);
    expect(result.totalRows).toBe(2);
  });

  it("respects maxRows parameter", () => {
    const text = "h1,h2\n" + Array.from({ length: 15 }, (_, i) => `${i},${i}`).join("\n");
    const result = parseCsvPreview(text, 5);
    expect(result.totalRows).toBe(15);
    expect(result.rows).toHaveLength(5);
  });

  it("handles quoted fields", () => {
    const result = parseCsvPreview('name,desc\n"Smith, John","hello world"\n');
    expect(result.rows[0]).toEqual(["Smith, John", "hello world"]);
  });

  it("handles empty input", () => {
    // empty string → split produces [""] → single empty header
    const result = parseCsvPreview("");
    expect(result.headers).toEqual([""]);
    expect(result.totalRows).toBe(0);
  });

  it("handles header-only CSV", () => {
    const result = parseCsvPreview("a,b,c\n");
    expect(result.headers).toEqual(["a", "b", "c"]);
    expect(result.totalRows).toBe(0);
    expect(result.rows).toEqual([]);
  });
});

// ── parseJsonPreview ─────────────────────────────────────────────
//    Main focus: comprehensive JSON edge-case coverage.

describe("parseJsonPreview", () => {
  // ── Happy paths ─────────────────────────────────────────────

  it("parses a flat array of objects", () => {
    const json = JSON.stringify([
      { b: 2, a: 1 },
      { b: 4, a: 3 },
    ]);
    const result = parseJsonPreview(json);
    // Columns sorted alphabetically: a, b
    expect(result.headers).toEqual(["a", "b"]);
    expect(result.rows).toEqual([
      ["1", "2"],
      ["3", "4"],
    ]);
    expect(result.totalRows).toBe(2);
  });

  it("parses wrapped {\"data\": [...]} format", () => {
    const json = JSON.stringify({
      data: [
        { b: 2, a: 1 },
        { b: 4, a: 3 },
      ],
    });
    const result = parseJsonPreview(json);
    expect(result.headers).toEqual(["a", "b"]);
    expect(result.rows).toEqual([
      ["1", "2"],
      ["3", "4"],
    ]);
    expect(result.totalRows).toBe(2);
  });

  // ── Determinism ─────────────────────────────────────────────

  it("produces same output regardless of JSON key order", () => {
    const a = JSON.stringify([{ b: 2, a: 1 }]);
    const b = JSON.stringify([{ a: 1, b: 2 }]);
    expect(parseJsonPreview(a)).toEqual(parseJsonPreview(b));
  });

  it("produces same output for wrapped with different key order", () => {
    const a = JSON.stringify({ data: [{ b: 2, a: 1 }] });
    const b = JSON.stringify({ data: [{ a: 1, b: 2 }] });
    expect(parseJsonPreview(a)).toEqual(parseJsonPreview(b));
  });

  // ── maxRows parameter ───────────────────────────────────────

  it("respects maxRows for preview rows but reports full totalRows", () => {
    const records = Array.from({ length: 15 }, (_, i) => ({ id: i }));
    const json = JSON.stringify(records);
    const result = parseJsonPreview(json, 3);
    expect(result.totalRows).toBe(15);
    expect(result.rows).toHaveLength(3);
  });

  // ── Inconsistent keys across records ────────────────────────

  it("collects all keys across records (union of keys)", () => {
    const json = JSON.stringify([
      { a: 1, b: 2 },
      { b: 4, c: 5 },
    ]);
    const result = parseJsonPreview(json);
    expect(result.headers).toEqual(["a", "b", "c"]);
    // Row 0: a=1, b=2, c=undefined → "1","2",""
    expect(result.rows[0]).toEqual(["1", "2", ""]);
    // Row 1: a=undefined, b=4, c=5 → "","4","5"
    expect(result.rows[1]).toEqual(["", "4", "5"]);
  });

  it("handles records with completely disjoint keys", () => {
    const json = JSON.stringify([
      { x: 1 },
      { y: 2 },
      { z: 3 },
    ]);
    const result = parseJsonPreview(json);
    expect(result.headers).toEqual(["x", "y", "z"]);
    expect(result.rows[0]).toEqual(["1", "", ""]);
    expect(result.rows[1]).toEqual(["", "2", ""]);
    expect(result.rows[2]).toEqual(["", "", "3"]);
  });

  // ── Single record ───────────────────────────────────────────

  it("handles a single record", () => {
    const json = JSON.stringify([{ a: 1, b: 2 }]);
    const result = parseJsonPreview(json);
    expect(result.headers).toEqual(["a", "b"]);
    expect(result.rows).toEqual([["1", "2"]]);
    expect(result.totalRows).toBe(1);
  });

  // ── Mixed value types ───────────────────────────────────────

  it("handles mixed string, number, and boolean values", () => {
    const json = JSON.stringify([
      { name: "Site A", ph: 7.2, active: true },
      { name: "Site B", ph: 8.1, active: false },
    ]);
    const result = parseJsonPreview(json);
    expect(result.headers).toEqual(["active", "name", "ph"]);
    expect(result.rows[0]).toEqual(["true", "Site A", "7.2"]);
    expect(result.rows[1]).toEqual(["false", "Site B", "8.1"]);
  });

  it("handles integer and float values", () => {
    const json = JSON.stringify([
      { count: 3, ratio: 1.5 },
      { count: 5, ratio: 2.7 },
    ]);
    const result = parseJsonPreview(json);
    expect(result.rows[0]).toEqual(["3", "1.5"]);
    expect(result.rows[1]).toEqual(["5", "2.7"]);
  });

  // ── Null / undefined ────────────────────────────────────────

  it("converts null values to empty strings", () => {
    const json = JSON.stringify([
      { a: 1, b: null },
      { a: null, b: 2 },
    ]);
    const result = parseJsonPreview(json);
    expect(result.rows[0]).toEqual(["1", ""]);
    expect(result.rows[1]).toEqual(["", "2"]);
  });

  it("handles all-null records", () => {
    const json = JSON.stringify([{ a: null, b: null }]);
    const result = parseJsonPreview(json);
    expect(result.rows[0]).toEqual(["", ""]);
  });

  // ── Empty string values ─────────────────────────────────────

  it("preserves empty string values", () => {
    const json = JSON.stringify([{ a: "", b: "hello" }]);
    const result = parseJsonPreview(json);
    expect(result.rows[0]).toEqual(["", "hello"]);
  });

  // ── Nested values (objects/arrays as cell values) ───────────

  it("stringifies nested objects as cell values", () => {
    const json = JSON.stringify([{ a: { nested: true }, b: 1 }]);
    const result = parseJsonPreview(json);
    // {nested:true} stringified → "[object Object]"
    expect(result.headers).toEqual(["a", "b"]);
    expect(result.rows[0]).toEqual(["[object Object]", "1"]);
  });

  it("stringifies arrays as cell values", () => {
    const json = JSON.stringify([{ a: [1, 2, 3], b: "x" }]);
    const result = parseJsonPreview(json);
    expect(result.rows[0]).toEqual(["1,2,3", "x"]);
  });

  // ── Non-object array elements ───────────────────────────────

  it("skips non-object records when collecting keys, yields empty rows for them", () => {
    // totalRows reflects parsed array length, not just valid-object rows
    const json = JSON.stringify([
      { a: 1 },
      42,
      { a: 2 },
    ]);
    const result = parseJsonPreview(json);
    // 42 is not an object → skipped in keySet; header comes only from {a:1},{a:2}
    expect(result.headers).toEqual(["a"]);
    expect(result.totalRows).toBe(3);
    // 42 as Record<string,unknown>["a"] → undefined → ""
    expect(result.rows[1]).toEqual([""]);
  });

  // ── Invalid JSON ────────────────────────────────────────────

  it("returns empty preview for invalid JSON syntax", () => {
    const result = parseJsonPreview("not valid json");
    expect(result).toEqual(emptyCsvPreview());
  });

  it("returns empty preview for incomplete JSON", () => {
    const result = parseJsonPreview('[{"a":1');
    expect(result).toEqual(emptyCsvPreview());
  });

  it("returns empty preview for trailing comma", () => {
    const result = parseJsonPreview('[{"a":1},]');
    expect(result).toEqual(emptyCsvPreview());
  });

  // ── Non-array, non-wrapped JSON ─────────────────────────────

  it("returns empty preview for a JSON object without data key", () => {
    const result = parseJsonPreview('{"just": "a dict"}');
    expect(result).toEqual(emptyCsvPreview());
  });

  it("returns empty preview for a JSON string", () => {
    const result = parseJsonPreview('"hello"');
    expect(result).toEqual(emptyCsvPreview());
  });

  it("returns empty preview for a JSON number", () => {
    const result = parseJsonPreview("42");
    expect(result).toEqual(emptyCsvPreview());
  });

  it("returns empty preview for JSON null", () => {
    const result = parseJsonPreview("null");
    expect(result).toEqual(emptyCsvPreview());
  });

  it("returns empty preview for JSON boolean", () => {
    const result = parseJsonPreview("true");
    expect(result).toEqual(emptyCsvPreview());
  });

  // ── Empty array ─────────────────────────────────────────────

  it("returns empty preview for empty JSON array", () => {
    const result = parseJsonPreview("[]");
    expect(result).toEqual(emptyCsvPreview());
  });

  it("returns empty preview for wrapped empty array", () => {
    const result = parseJsonPreview('{"data": []}');
    expect(result).toEqual(emptyCsvPreview());
  });

  // ── Wrapped with non-array data ─────────────────────────────

  it("returns empty preview when data key value is a string", () => {
    const result = parseJsonPreview('{"data": "not an array"}');
    expect(result).toEqual(emptyCsvPreview());
  });

  it("returns empty preview when data key value is a number", () => {
    const result = parseJsonPreview('{"data": 42}');
    expect(result).toEqual(emptyCsvPreview());
  });

  it("returns empty preview when data key value is null", () => {
    const result = parseJsonPreview('{"data": null}');
    expect(result).toEqual(emptyCsvPreview());
  });

  it("returns empty preview when data key value is an object", () => {
    const result = parseJsonPreview('{"data": {"a": 1}}');
    expect(result).toEqual(emptyCsvPreview());
  });

  // ── Wrapped with extra keys ─────────────────────────────────

  it("ignores extra keys alongside data in wrapped format", () => {
    const json = JSON.stringify({
      data: [{ a: 1 }],
      meta: "ignored",
      version: 2,
    });
    const result = parseJsonPreview(json);
    expect(result.headers).toEqual(["a"]);
    expect(result.totalRows).toBe(1);
  });

  // ── Deeply nested structure (no data key) ───────────────────

  it("returns empty for deeply nested JSON without data key", () => {
    const json = JSON.stringify({
      outer: {
        inner: [{ a: 1 }],
      },
    });
    const result = parseJsonPreview(json);
    expect(result).toEqual(emptyCsvPreview());
  });

  // ── Whitespace handling ─────────────────────────────────────

  it("handles prettified JSON with extra whitespace", () => {
    const json = `[
      { "a" : 1 , "b" : 2 },
      { "a" : 3 , "b" : 4 }
    ]`;
    const result = parseJsonPreview(json);
    expect(result.headers).toEqual(["a", "b"]);
    expect(result.totalRows).toBe(2);
  });

  it("handles empty string input", () => {
    const result = parseJsonPreview("");
    expect(result).toEqual(emptyCsvPreview());
  });

  // ── Large number of records ─────────────────────────────────

  it("defaults maxRows to 10 when not specified", () => {
    const records = Array.from({ length: 15 }, (_, i) => ({ id: i }));
    const json = JSON.stringify(records);
    const result = parseJsonPreview(json);
    expect(result.totalRows).toBe(15);
    expect(result.rows).toHaveLength(10);
  });

  it("handles a large number of records efficiently", () => {
    const records = Array.from({ length: 1000 }, (_, i) => ({
      id: i,
      value: `row-${i}`,
    }));
    const json = JSON.stringify(records);
    const result = parseJsonPreview(json, 10);
    expect(result.totalRows).toBe(1000);
    expect(result.rows).toHaveLength(10);
    expect(result.headers).toEqual(["id", "value"]);
  });
});

// ── Helper ───────────────────────────────────────────────────────

function emptyCsvPreview(): CsvPreview {
  return { headers: [], rows: [], totalRows: 0 };
}
