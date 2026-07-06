/** Client-side CSV parsing and preview helpers. */

export interface CsvPreview {
  headers: string[];
  rows: string[][];
  totalRows: number;
}

const MAX_PREVIEW_SIZE = 50 * 1024 * 1024; // 50 MB

export function validateCsvFile(file: File): string | null {
  if (!file.name.endsWith(".csv")) {
    return "File must be a .csv";
  }
  if (file.size === 0) {
    return "File is empty";
  }
  if (file.size > MAX_PREVIEW_SIZE) {
    return `File too large (max ${MAX_PREVIEW_SIZE / 1024 / 1024} MB)`;
  }
  return null;
}

export function parseCsvPreview(text: string, maxRows: number = 10): CsvPreview {
  const lines = text.trim().split("\n");
  if (lines.length === 0) return { headers: [], rows: [], totalRows: 0 };

  const headers = parseCsvLine(lines[0]);
  const rows = lines.slice(1, maxRows + 1).map(parseCsvLine);
  const totalRows = lines.length - 1;

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
