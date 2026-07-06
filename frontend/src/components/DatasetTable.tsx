import { Link } from "react-router-dom";
import AnomalyBadge from "./AnomalyBadge";
import TxExplorerLink from "./TxExplorerLink";
import type { DatasetResponse } from "../types";

interface Props {
  datasets: DatasetResponse[];
  loading: boolean;
  error: string | null;
}

export default function DatasetTable({ datasets, loading, error }: Props) {
  if (loading) {
    return (
      <div className="text-center py-12">
        <div className="animate-spin w-6 h-6 border-2 border-stellar border-t-transparent rounded-full mx-auto mb-3" />
        <p className="text-gray-500 text-sm">Loading datasets...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">
        {error}
      </div>
    );
  }

  if (datasets.length === 0) {
    return (
      <div className="text-center py-12">
        <svg
          className="mx-auto h-12 w-12 text-gray-300 mb-4"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"
          />
        </svg>
        <p className="text-gray-500">No datasets anchored yet.</p>
        <Link
          to="/upload"
          className="inline-block mt-3 text-sm text-stellar hover:underline"
        >
          Upload your first dataset
        </Link>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 bg-gray-50">
            <th className="px-4 py-3 text-left font-medium text-gray-600">Date</th>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Dataset</th>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Hash</th>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Anomaly</th>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Status</th>
            <th className="px-4 py-3 text-left font-medium text-gray-600">TX</th>
          </tr>
        </thead>
        <tbody>
          {datasets.map((ds) => (
            <tr
              key={ds.dataset_id}
              className="border-b border-gray-100 hover:bg-gray-50 transition-colors"
            >
              <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
                {new Date(ds.created_at).toLocaleDateString()}
              </td>
              <td className="px-4 py-3">
                <Link
                  to={`/datasets/${ds.dataset_id}`}
                  className="text-stellar hover:underline font-medium"
                >
                  {ds.dataset_id.slice(0, 8)}...
                </Link>
              </td>
              <td className="px-4 py-3">
                <code className="text-xs font-mono text-gray-500">
                  {ds.dataset_hash.slice(0, 12)}...
                </code>
              </td>
              <td className="px-4 py-3">
                <AnomalyBadge score={ds.anomaly_score} />
              </td>
              <td className="px-4 py-3">
                <span
                  className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full ${
                    ds.status === "anchored"
                      ? "bg-green-100 text-green-800"
                      : ds.status === "failed"
                        ? "bg-red-100 text-red-800"
                        : "bg-yellow-100 text-yellow-800"
                  }`}
                >
                  {ds.status === "anchored" && (
                    <svg className="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                  {ds.status === "pending" ? "Pending" : ds.status === "anchored" ? "Anchored" : "Failed"}
                </span>
              </td>
              <td className="px-4 py-3">
                {ds.stellar_tx_hash ? (
                  <TxExplorerLink txHash={ds.stellar_tx_hash} />
                ) : (
                  <span className="text-gray-300">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
