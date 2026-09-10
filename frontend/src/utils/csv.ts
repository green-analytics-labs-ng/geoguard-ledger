/** Client-side CSV and JSON file parsing and preview helpers. */

export interface CsvPreview {
  headers: string[];
  rows: string[][];
  totalRows: number;
}

const MAX_PREVIEW_SIZE = 50 * 1024 * 1024; // 50 MB
const SUPPORTED_EXTENSIONS = [".csv", ".json"];

/** Check if a filename has a supported extension. */
export function isSupportedFormat(filename: string): boolean {
  return SUPPORTED_EXTENSIONS.some((ext) =>
    filename.toLowerCase().endsWith(ext),
  );
}

/** Validate a data file (CSV or JSON) for size and format. */
export function validateDataFile(file: File): string | null {
  if (!isSupportedFormat(file.name)) {
    return "File must be a .csv or .json";
  }
  if (file.size === 0) {
    return "File is empty";
  }
  if (file.size > MAX_PREVIEW_SIZE) {
    return `File too large (max ${MAX_PREVIEW_SIZE / 1024 / 1024} MB)`;
  }
  return null;
}

/** @deprecated Use validateDataFile instead. */
export function validateCsvFile(file: File): string | null {
  return validateDataFile(file);
}

/**
 * Parse delimited text into rows, following RFC 4180.
 *
 * Unlike a naive "toggle on every quote" approach, this handles:
 * - quoted fields containing the delimiter (`,`, newlines, or quotes);
 * - escaped quotes inside a quoted field (`""` becomes a single `"`);
 * - LF, CRLF and CR line endings, including newlines inside quoted fields.
 *
 * Cells are trimmed to match the backend, whose canonicalization strips
 * whitespace from every cell before hashing, so the preview reflects what is
 * actually anchored.
 */
export function parseCsvRows(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let inQuotes = false;
  let fieldWasQuoted = false;

  const pushField = (): void => {
    row.push(field.trim());
    field = "";
    fieldWasQuoted = false;
  };

  const pushRow = (): void => {
    pushField();
    rows.push(row);
    row = [];
  };

  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];

    if (inQuotes) {
      if (char === '"') {
        if (text[i + 1] === '"') {
          // Escaped quote: emit one quote and skip its pair.
          field += '"';
          i += 1;
        } else {
          inQuotes = false;
        }
      } else {
        field += char;
      }
      continue;
    }

    if (char === '"') {
      inQuotes = true;
      fieldWasQuoted = true;
    } else if (char === ",") {
      pushField();
    } else if (char === "\r" || char === "\n") {
      // Treat CRLF as a single line break.
      if (char === "\r" && text[i + 1] === "\n") i += 1;
      pushRow();
    } else {
      field += char;
    }
  }

  // Flush the trailing field unless the input ended on a line break.
  if (field !== "" || row.length > 0 || fieldWasQuoted) {
    pushRow();
  }

  return rows;
}

/**
 * Parse CSV text into a preview structure.
 *
 * Blank lines are ignored so a trailing newline does not inflate `totalRows`.
 */
export function parseCsvPreview(text: string, maxRows: number = 10): CsvPreview {
  const rows = parseCsvRows(text);
  const [headers = [], ...dataRows] = rows;

  const populatedRows = dataRows.filter(
    (row) => !(row.length === 1 && row[0] === ""),
  );

  return {
    headers,
    rows: populatedRows.slice(0, maxRows),
    totalRows: populatedRows.length,
  };
}

/** Parse JSON text into a preview structure matching the backend parser.
 *  Supports flat arrays and {"data": [...]} wrapped objects.
 *  Columns are sorted alphabetically to match the backend's canonical CSV. */
export function parseJsonPreview(text: string, maxRows: number = 10): CsvPreview {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    return { headers: [], rows: [], totalRows: 0 };
  }

  // Normalize to array of record objects
  let records: Record<string, unknown>[];
  if (Array.isArray(parsed)) {
    records = parsed as Record<string, unknown>[];
  } else if (
    parsed !== null &&
    typeof parsed === "object" &&
    "data" in parsed &&
    Array.isArray((parsed as Record<string, unknown>).data)
  ) {
    records = (parsed as Record<string, unknown>).data as Record<string, unknown>[];
  } else {
    return { headers: [], rows: [], totalRows: 0 };
  }

  if (records.length === 0) {
    return { headers: [], rows: [], totalRows: 0 };
  }

  // Collect all keys across all records
  const keySet = new Set<string>();
  for (const record of records) {
    if (record !== null && typeof record === "object") {
      for (const key of Object.keys(record)) {
        keySet.add(key);
      }
    }
  }

  // Sort alphabetically to match backend behavior
  const headers = Array.from(keySet).sort();
  const totalRows = records.length;
  const previewRecords = records.slice(0, maxRows);

  const rows: string[][] = previewRecords.map((record) =>
    headers.map((key) => {
      const val = (record as Record<string, unknown>)[key];
      if (val === null || val === undefined) return "";
      return String(val);
    }),
  );

  return { headers, rows, totalRows };
}

