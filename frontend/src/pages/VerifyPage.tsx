import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useVerify } from "../hooks/useVerify";
import VerificationResult, {
  VerificationResultEmpty,
} from "../components/VerificationResult";
import WalletConnector from "../components/WalletConnector";
import { validateCsvFile } from "../utils/csv";

export default function VerifyPage() {
  const navigate = useNavigate();
  const { result, loading, error, verify, clear } = useVerify();

  const [hashInput, setHashInput] = useState("");
  const [mode, setMode] = useState<"hash" | "file">("hash");
  const [fileError, setFileError] = useState<string | null>(null);

  const handleHashSubmit = useCallback(() => {
    const trimmed = hashInput.trim();
    if (trimmed.length !== 64 || !/^[0-9a-f]{64}$/i.test(trimmed)) {
      setFileError("Hash must be a 64-character hexadecimal string (SHA-256)");
      return;
    }
    setFileError(null);
    verify(trimmed);
  }, [hashInput, verify]);

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

      const validationError = validateCsvFile(file);
      if (validationError) {
        setFileError(validationError);
        return;
      }
      setFileError(null);
      verify(file);
    },
    [verify],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") handleHashSubmit();
    },
    [handleHashSubmit],
  );

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-200 px-4 py-3">
        <div className="max-w-3xl mx-auto flex justify-between items-center">
          <button
            onClick={() => navigate("/")}
            className="text-sm text-gray-500 hover:text-stellar transition-colors"
          >
            &larr; Dashboard
          </button>
          <WalletConnector compact />
        </div>
      </nav>

      <div className="max-w-3xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold text-stellar mb-2">
          Verify Dataset
        </h1>
        <p className="text-sm text-gray-500 mb-8">
          Check whether a dataset's integrity proof exists on the Stellar
          blockchain.
        </p>

        {/* Mode selector */}
        <div className="flex gap-2 mb-6">
          <button
            onClick={() => {
              setMode("hash");
              clear();
              setFileError(null);
            }}
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
              mode === "hash"
                ? "bg-stellar text-white"
                : "bg-white text-gray-600 border border-gray-200 hover:bg-gray-50"
            }`}
          >
            By Hash
          </button>
          <button
            onClick={() => {
              setMode("file");
              clear();
              setFileError(null);
            }}
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
              mode === "file"
                ? "bg-stellar text-white"
                : "bg-white text-gray-600 border border-gray-200 hover:bg-gray-50"
            }`}
          >
            By File Upload
          </button>
        </div>

        {/* Hash input */}
        {mode === "hash" && (
          <div className="card mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Dataset Hash (SHA-256)
            </label>
            <div className="flex gap-3">
              <input
                type="text"
                value={hashInput}
                onChange={(e) => setHashInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Paste a 64-character hex hash..."
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-stellar focus:border-transparent"
                maxLength={64}
              />
              <button
                onClick={handleHashSubmit}
                disabled={loading || hashInput.trim().length === 0}
                className="btn-primary"
              >
                {loading ? "Verifying..." : "Verify"}
              </button>
            </div>
          </div>
        )}

        {/* File upload */}
        {mode === "file" && (
          <div className="card mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Upload CSV to Re-Compute Hash
            </label>
            <input
              type="file"
              accept=".csv"
              onChange={handleFileSelect}
              className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-stellar file:text-white hover:file:bg-blue-700 file:cursor-pointer file:transition-colors"
            />
            {loading && (
              <div className="mt-3 flex items-center gap-2 text-sm text-gray-500">
                <span className="animate-spin w-4 h-4 border-2 border-stellar border-t-transparent rounded-full" />
                Computing hash and verifying...
              </div>
            )}
          </div>
        )}

        {/* Error */}
        {(error || fileError) && (
          <div className="mb-6 bg-red-50 border border-red-200 text-red-700 rounded-lg p-4 text-sm">
            {error || fileError}
          </div>
        )}

        {/* Result */}
        <div className="card">
          {result ? (
            <VerificationResult result={result} />
          ) : (
            <VerificationResultEmpty />
          )}
        </div>
      </div>
    </div>
  );
}
