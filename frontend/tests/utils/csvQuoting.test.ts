/**
 * RFC 4180 quoting tests.
 *
 * The previous parser toggled `inQuotes` on every `"`, so an escaped quote
 * (`""`) flipped the parser state and corrupted every subsequent field. A CSV
 * preview could therefore disagree with what the backend's `csv.reader`
 * parsed - and therefore with what was actually hashed and anchored.
 */

import { describe, it, expect } from "vitest";
import { parseCsvPreview, parseCsvRows } from "../../src/utils/csv";

describe("parseCsvRows", () => {
  it("decodes an escaped quote inside a quoted field", () => {
    // "Hello ""world""" must become: Hello "world"
    expect(parseCsvRows('"Hello ""world""",42')).toEqual([
      ['Hello "world"', "42"],
    ]);
  });

  it("keeps a doubled quote as a literal single quote", () => {
    expect(parseCsvRows('a,"say ""hi"" now"')).toEqual([
      ["a", 'say "hi" now'],
    ]);
  });

  it("treats a delimiter inside quotes as content", () => {
    expect(parseCsvRows('"Zaria, Kaduna",NG')).toEqual([
      ["Zaria, Kaduna", "NG"],
    ]);
  });

  it("treats a newline inside quotes as content", () => {
    expect(parseCsvRows('name,note\n"Site A","line one\nline two"')).toEqual([
      ["name", "note"],
      ["Site A", "line one\nline two"],
    ]);
  });

  it("handles CRLF line endings", () => {
    expect(parseCsvRows("a,b\r\n1,2\r\n")).toEqual([
      ["a", "b"],
      ["1", "2"],
    ]);
  });

  it("handles a quoted field containing a delimiter and an escaped quote", () => {
    expect(parseCsvRows('"a, ""b""",c')).toEqual([['a, "b"', "c"]]);
  });

  it("preserves empty quoted fields", () => {
    expect(parseCsvRows('a,"",c')).toEqual([["a", "", "c"]]);
  });

  it("does not emit a row for a trailing newline", () => {
    expect(parseCsvRows("a,b\n")).toEqual([["a", "b"]]);
  });

  it("returns nothing for empty input", () => {
    expect(parseCsvRows("")).toEqual([]);
  });
});

describe("parseCsvPreview", () => {
  it("keeps escaped quotes intact end to end", () => {
    const result = parseCsvPreview('name,note\n"Site ""A""",ok\n');
    expect(result.headers).toEqual(["name", "note"]);
    expect(result.rows).toEqual([['Site "A"', "ok"]]);
    expect(result.totalRows).toBe(1);
  });

  it("does not lose columns after an escaped quote", () => {
    const result = parseCsvPreview('a,b,c\n"x ""y""",2,3\n');
    expect(result.rows[0]).toEqual(['x "y"', "2", "3"]);
  });

  it("counts a multi-line quoted record as one row", () => {
    const result = parseCsvPreview('id,note\n1,"first\nsecond"\n2,"plain"\n');
    expect(result.totalRows).toBe(2);
    expect(result.rows[0]).toEqual(["1", "first\nsecond"]);
    expect(result.rows[1]).toEqual(["2", "plain"]);
  });

  it("ignores blank lines rather than counting them as rows", () => {
    const result = parseCsvPreview("a,b\n1,2\n\n");
    expect(result.totalRows).toBe(1);
    expect(result.headers).toEqual(["a", "b"]);
  });

  it("respects maxRows while still reporting the full row count", () => {
    const text =
      "h1,h2\n" + Array.from({ length: 20 }, (_, i) => `${i},${i}`).join("\n");
    const result = parseCsvPreview(text, 3);
    expect(result.totalRows).toBe(20);
    expect(result.rows).toHaveLength(3);
  });
});
