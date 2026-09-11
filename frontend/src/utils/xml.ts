/** Client-side XML parsing and preview helpers. */

import type { CsvPreview } from "./csv";

function emptyPreview(): CsvPreview {
  return { headers: [], rows: [], totalRows: 0 };
}

/**
 * Parse XML into a preview structure.
 *
 * Mirrors the backend's flattening convention (`pandas.read_xml` with its
 * default `xpath`): every direct child of the document root becomes a row, and
 * that element's attributes plus child-element text become columns. Columns are
 * collected in first-seen order so the preview lines up with the DataFrame the
 * backend analyses.
 *
 * @param text Raw XML file content.
 * @param maxRows Maximum number of preview rows to return.
 * @returns A preview, or an empty preview when the document is malformed or has
 *          no repeating child elements.
 */
export function parseXmlPreview(text: string, maxRows: number = 10): CsvPreview {
  const doc = new DOMParser().parseFromString(text, "application/xml");

  // Browsers (and jsdom) report XML syntax errors in a `parsererror` element.
  if (doc.getElementsByTagName("parsererror").length > 0) {
    return emptyPreview();
  }

  const root = doc.documentElement;
  if (!root) return emptyPreview();

  const records = Array.from(root.children);
  if (records.length === 0) return emptyPreview();

  const headers: string[] = [];
  const seen = new Set<string>();

  for (const record of records) {
    for (const attribute of Array.from(record.attributes)) {
      if (!seen.has(attribute.name)) {
        seen.add(attribute.name);
        headers.push(attribute.name);
      }
    }
    for (const child of Array.from(record.children)) {
      if (!seen.has(child.tagName)) {
        seen.add(child.tagName);
        headers.push(child.tagName);
      }
    }
  }

  if (headers.length === 0) return emptyPreview();

  return {
    headers,
    rows: records
      .slice(0, maxRows)
      .map((record) => headers.map((header) => cellValue(record, header))),
    totalRows: records.length,
  };
}

/** Read one cell from a record element, preferring an attribute over a child. */
function cellValue(record: Element, header: string): string {
  const attribute = record.getAttribute(header);
  if (attribute !== null) return attribute.trim();

  const child = Array.from(record.children).find(
    (element) => element.tagName === header,
  );
  if (!child) return "";

  return (child.textContent ?? "").trim();
}
