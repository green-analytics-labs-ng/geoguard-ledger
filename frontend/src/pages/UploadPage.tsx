import { useState } from "react";
import { useNavigate } from "react-router-dom";
import BatchAnchorFlow from "../components/BatchAnchorFlow";
import SingleAnchorFlow from "../components/SingleAnchorFlow";
import WalletConnector from "../components/WalletConnector";

type AnchorMode = "single" | "batch";

export default function UploadPage() {
  const navigate = useNavigate();

  // Anchor one dataset directly, or commit several datasets to a single
  // Merkle root. Single-dataset anchoring stays the default.
  const [mode, setMode] = useState<AnchorMode>("single");

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
        <h1 className="text-2xl font-bold text-stellar mb-2">Upload Dataset</h1>
        <p className="text-sm text-gray-500 mb-6">
          {mode === "single"
            ? "Upload a geochemical dataset (CSV, JSON, or XML). The data will be hashed, analyzed for anomalies, and anchored to the Stellar blockchain."
            : "Upload several datasets and anchor them together under a single Merkle root — one on-chain entry for the whole batch."}
        </p>

        {/* Mode selector */}
        <div className="flex gap-2 mb-8">
          <button
            onClick={() => setMode("single")}
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
              mode === "single"
                ? "bg-stellar text-white"
                : "bg-white text-gray-600 border border-gray-200 hover:bg-gray-50"
            }`}
          >
            Single Dataset
          </button>
          <button
            onClick={() => setMode("batch")}
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
              mode === "batch"
                ? "bg-stellar text-white"
                : "bg-white text-gray-600 border border-gray-200 hover:bg-gray-50"
            }`}
          >
            Batch (Merkle Root)
          </button>
        </div>

        {mode === "batch" ? <BatchAnchorFlow /> : <SingleAnchorFlow />}
      </div>
    </div>
  );
}
