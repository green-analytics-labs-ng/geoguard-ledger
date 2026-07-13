import { useState, useRef, useCallback, type DragEvent, type ChangeEvent } from "react";
import {
  validateDataFile,
  parseCsvPreview,
  parseJsonPreview,
  type CsvPreview,
} from "../utils/csv";

interface Props {
  onFileSelected: (file: File, preview: CsvPreview) => void;
}

export default function CsvDropzone({ onFileSelected }: Props) {
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<CsvPreview | null>(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const processFile = useCallback(
    (file: File) => {
      setError(null);
      setPreview(null);

      const validationError = validateDataFile(file);
      if (validationError) {
        setError(validationError);
        return;
      }

      const isJson = file.name.toLowerCase().endsWith(".json");

      const reader = new FileReader();
      reader.onload = () => {
        const text = reader.result as string;
        const parsed = isJson ? parseJsonPreview(text) : parseCsvPreview(text);
        if (parsed.headers.length === 0) {
          setError(
            isJson
              ? 'Could not parse JSON — expected an array of objects or a {"data": [...]} wrapper'
              : "Could not parse CSV headers",
          );
          return;
        }
        if (parsed.totalRows === 0) {
          setError(
            isJson ? "JSON data is empty" : "CSV has no data rows",
          );
          return;
        }
        setPreview(parsed);
        onFileSelected(file, parsed);
      };
      reader.onerror = () => {
        setError("Failed to read file");
      };
      reader.readAsText(file);
    },
    [onFileSelected],
  );

  const handleDrop = useCallback(
    (e: DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) processFile(file);
    },
    [processFile],
  );

  const handleDragOver = useCallback((e: DragEvent) => {
    e.preventDefault();
    setDragging(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setDragging(false);
  }, []);

  const handleInputChange = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) processFile(file);
    },
    [processFile],
  );

  return (
    <div className="space-y-4">
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => inputRef.current?.click()}
        className={`
          border-2 border-dashed rounded-xl p-12 text-center cursor-pointer
          transition-colors duration-200
          ${
            dragging
              ? "border-stellar bg-blue-50"
              : "border-gray-300 hover:border-gray-400 hover:bg-gray-50"
          }
        `}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv,.json"
          className="hidden"
          onChange={handleInputChange}
        />
        <svg
          className="mx-auto h-12 w-12 text-gray-400 mb-4"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
          />
        </svg>
        <p className="text-gray-600 font-medium">
          {dragging
            ? "Drop your data file here"
            : "Drop a CSV or JSON file here, or click to browse"}
        </p>
        <p className="text-gray-400 text-sm mt-1">
          .csv or .json files (max 50 MB)
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 text-sm">
          {error}
        </div>
      )}

      {preview && (
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <div className="px-4 py-2 bg-gray-50 border-b border-gray-200 text-sm text-gray-600 flex justify-between">
            <span>
              {preview.totalRows} row{preview.totalRows !== 1 ? "s" : ""}
            </span>
            <span>
              {preview.headers.length} column{preview.headers.length !== 1 ? "s" : ""}
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50">
                  {preview.headers.map((h, i) => (
                    <th key={i} className="px-4 py-2 text-left font-medium text-gray-600 border-r last:border-r-0">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview.rows.slice(0, 5).map((row, ri) => (
                  <tr key={ri} className="border-t border-gray-100 hover:bg-gray-50">
                    {row.map((cell, ci) => (
                      <td key={ci} className="px-4 py-2 text-gray-700 border-r last:border-r-0 truncate max-w-[200px]">
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {preview.totalRows > 5 && (
            <div className="px-4 py-2 bg-gray-50 border-t border-gray-200 text-xs text-gray-400">
              Showing first 5 of {preview.totalRows} rows
            </div>
          )}
        </div>
      )}
    </div>
  );
}
