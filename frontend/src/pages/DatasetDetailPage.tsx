import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useWallet } from "../context/WalletContext";
import { getDataset } from "../api/datasets";
import AnomalyBadge from "../components/AnomalyBadge";
import TxExplorerLink from "../components/TxExplorerLink";
import WalletConnector from "../components/WalletConnector";
import type { DatasetResponse } from "../types";

export default function DatasetDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { network } = useWallet();

  const [dataset, setDataset] = useState<DatasetResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDataset = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getDataset(id);
      setDataset(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load dataset",
      );
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchDataset();
  }, [fetchDataset]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin w-8 h-8 border-2 border-stellar border-t-transparent rounded-full mx-auto mb-3" />
          <p className="text-gray-500 text-sm">Loading dataset...</p>
        </div>
      </div>
    );
  }

  if (error || !dataset) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-3xl mx-auto">
          <button
            onClick={() => navigate("/datasets")}
            className="text-sm text-gray-500 hover:text-stellar transition-colors mb-6"
          >
            &larr; Back to Datasets
          </button>
          <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
            <p className="text-red-700">{error || "Dataset not found"}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-200 px-4 py-3">
        <div className="max-w-3xl mx-auto flex justify-between items-center">
          <button
            onClick={() => navigate("/datasets")}
            className="text-sm text-gray-500 hover:text-stellar transition-colors"
          >
            &larr; Back to Datasets
          </button>
          <WalletConnector compact />
        </div>
      </nav>

      <div className="max-w-3xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="flex items-start justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-stellar mb-1">
              Dataset Details
            </h1>
            <p className="text-sm text-gray-500 font-mono">ID: {id}</p>
          </div>
          <AnomalyBadge score={dataset.anomaly_score} size="md" showLabel />
        </div>

        {/* Record Details */}
        <div className="card space-y-6">
          {/* Status */}
          <div className="flex justify-between items-center">
            <span className="text-sm text-gray-500">Status</span>
            <span
              className={`inline-flex items-center px-3 py-1 text-sm font-medium rounded-full ${
                dataset.status === "anchored"
                  ? "bg-green-100 text-green-800"
                  : dataset.status === "failed"
                    ? "bg-red-100 text-red-800"
                    : "bg-yellow-100 text-yellow-800"
              }`}
            >
              {dataset.status === "pending"
                ? "Pending"
                : dataset.status === "anchored"
                  ? "Anchored"
                  : "Failed"}
            </span>
          </div>

          <hr className="border-gray-100" />

          {/* Hash */}
          <div>
            <p className="text-xs text-gray-500 mb-1">Dataset Hash (SHA-256)</p>
            <code className="text-sm font-mono text-gray-700 break-all bg-gray-50 px-3 py-2 rounded block">
              {dataset.dataset_hash}
            </code>
          </div>

          <hr className="border-gray-100" />

          {/* Grid */}
          <div className="grid grid-cols-2 gap-6">
            <div>
              <p className="text-xs text-gray-500 mb-1">Created</p>
              <p className="text-sm text-gray-700">
                {new Date(dataset.created_at).toLocaleString()}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">Anchored</p>
              <p className="text-sm text-gray-700">
                {dataset.anchored_at
                  ? new Date(dataset.anchored_at).toLocaleString()
                  : "—"}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">Anomaly Score</p>
              <AnomalyBadge score={dataset.anomaly_score} size="md" />
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">Transaction</p>
              {dataset.stellar_tx_hash ? (
                <TxExplorerLink
                  txHash={dataset.stellar_tx_hash}
                  network={network ?? "testnet"}
                />
              ) : (
                <span className="text-sm text-gray-300">—</span>
              )}
            </div>
          </div>

          {dataset.explorer_url && (
            <>
              <hr className="border-gray-100" />
              <div>
                <p className="text-xs text-gray-500 mb-1">
                  Explorer Link
                </p>
                <a
                  href={dataset.explorer_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-stellar hover:underline"
                >
                  View on Stellar Expert &rarr;
                </a>
              </div>
            </>
          )}
        </div>

        {/* Actions */}
        <div className="flex gap-3 mt-6">
          <Link
            to={`/verify${dataset.stellar_tx_hash ? `?dataset_hash=${dataset.dataset_hash}` : ""}`}
            className="btn-primary"
          >
            Verify On-Chain
          </Link>
          <Link to="/datasets" className="btn-secondary">
            All Datasets
          </Link>
        </div>
      </div>
    </div>
  );
}
