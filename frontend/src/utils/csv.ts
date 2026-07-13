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

/** Parse CSV text into a preview structure. */
export function parseCsvPreview(text: string, maxRows: number = 10): CsvPreview {
  const lines = text.trim().split("\n");
  if (lines.length === 0) return { headers: [], rows: [], totalRows: 0 };

  const headers = parseCsvLine(lines[0]);
  const rows = lines.slice(1, maxRows + 1).map(parseCsvLine);
  const totalRows = lines.length - 1;

  return { headers, rows, totalRows };
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

function parseCsvLine(line: string): string[] {
  const cells: string[] = [];
  let current = "";
  let inQuotes = false;

  for (const char of line) {
    if (char === '"') {
      inQuotes = !inQuotes;
    } else if (char === "," && !inQuotes) {
      cells.push(current.trim());
      current = "";
    } else {
      current += char;
    }
  }
  cells.push(current.trim());
  return cells;
}
