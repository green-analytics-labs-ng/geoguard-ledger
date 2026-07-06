import { useNavigate } from "react-router-dom";
import { useDatasets } from "../hooks/useDatasets";
import DatasetTable from "../components/DatasetTable";
import WalletConnector from "../components/WalletConnector";

export default function DatasetListPage() {
  const navigate = useNavigate();
  const { datasets, loading, error } = useDatasets();

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-200 px-4 py-3">
        <div className="max-w-7xl mx-auto flex justify-between items-center">
          <button
            onClick={() => navigate("/")}
            className="text-sm text-gray-500 hover:text-stellar transition-colors"
          >
            &larr; Dashboard
          </button>
          <WalletConnector compact />
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="flex justify-between items-center mb-6">
          <div>
            <h1 className="text-2xl font-bold text-stellar">Datasets</h1>
            <p className="text-sm text-gray-500 mt-1">
              {loading
                ? "Loading..."
                : `${datasets.length} dataset${datasets.length !== 1 ? "s" : ""} anchored`}
            </p>
          </div>
          <button
            onClick={() => navigate("/upload")}
            className="btn-primary"
          >
            Upload New Dataset
          </button>
        </div>

        <div className="card">
          <DatasetTable datasets={datasets} loading={loading} error={error} />
        </div>
      </div>
    </div>
  );
}
