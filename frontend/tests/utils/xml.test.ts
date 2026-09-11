import { describe, it, expect } from "vitest";
import { parseXmlPreview } from "../../src/utils/xml";

const SAMPLE_XML = `<?xml version="1.0" encoding="UTF-8"?>
<!-- exported by LIMS -->
<GeochemistryReport generated="2026-07-05T12:00:00Z">
  <sample id="S001" latitude="34.052200" longitude="-118.243700">
    <pH>7.20</pH>
    <conductivity>450.00</conductivity>
  </sample>
  <sample id="S002" latitude="34.052500" longitude="-118.244000">
    <pH>7.15</pH>
    <conductivity>452.00</conductivity>
  </sample>
</GeochemistryReport>`;

function emptyPreview() {
  return { headers: [], rows: [], totalRows: 0 };
}

describe("parseXmlPreview", () => {
  it("treats each direct child of the root as a row", () => {
    const result = parseXmlPreview(SAMPLE_XML);
    expect(result.totalRows).toBe(2);
    expect(result.rows).toHaveLength(2);
  });

  it("collects attributes and child elements as columns", () => {
    const result = parseXmlPreview(SAMPLE_XML);
    expect(result.headers).toEqual(["id", "latitude", "longitude", "pH", "conductivity"]);
  });

  it("reads attribute and element values into the right cells", () => {
    const result = parseXmlPreview(SAMPLE_XML);
    expect(result.rows[0]).toEqual(["S001", "34.052200", "-118.243700", "7.20", "450.00"]);
    expect(result.rows[1][0]).toBe("S002");
  });

  it("ignores comments, whitespace and the XML declaration", () => {
    const result = parseXmlPreview(SAMPLE_XML);
    expect(result.headers).not.toContain("generated");
  });

  it("respects maxRows while reporting the full row count", () => {
    const rows = Array.from({ length: 25 }, (_, i) => `<sample id="S${i}"><pH>7</pH></sample>`);
    const xml = `<report>${rows.join("")}</report>`;

    const result = parseXmlPreview(xml, 3);

    expect(result.totalRows).toBe(25);
    expect(result.rows).toHaveLength(3);
  });

  it("returns an empty preview for malformed XML", () => {
    expect(parseXmlPreview("<report><sample></report>")).toEqual(emptyPreview());
  });

  it("returns an empty preview for empty input", () => {
    expect(parseXmlPreview("")).toEqual(emptyPreview());
  });

  it("returns an empty preview when the root has no children", () => {
    expect(parseXmlPreview("<report></report>")).toEqual(emptyPreview());
  });

  it("handles self-closing records", () => {
    const result = parseXmlPreview('<report><row a="1"/><row a="2"/></report>');
    expect(result.headers).toEqual(["a"]);
    expect(result.rows).toEqual([["1"], ["2"]]);
  });

  it("leaves missing values empty rather than dropping the row", () => {
    const xml = '<report><row a="1"/><row b="2"/></report>';
    const result = parseXmlPreview(xml);

    expect(result.headers).toEqual(["a", "b"]);
    expect(result.rows[0]).toEqual(["1", ""]);
    expect(result.rows[1]).toEqual(["", "2"]);
  });
});
