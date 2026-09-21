import { Link } from "react-router-dom";

export default function DashboardPage() {
  // The header, its navigation, and the wallet connector belong to AppLayout
  // now; this page only supplies its own content.
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 className="text-2xl font-bold text-stellar mb-6">Dashboard</h1>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="card">
          <p className="text-sm text-gray-500">Total Anchored</p>
          <p className="text-3xl font-bold text-stellar">0</p>
        </div>
        <div className="card">
          <p className="text-sm text-gray-500">Recent Submissions</p>
          <p className="text-3xl font-bold text-stellar">0</p>
        </div>
        <div className="card">
          <p className="text-sm text-gray-500">Anomaly Rate</p>
          <p className="text-3xl font-bold text-stellar">—</p>
        </div>
      </div>

      <div className="card">
        <h2 className="text-lg font-semibold mb-4">Quick Actions</h2>
        <div className="flex gap-4">
          <Link to="/upload" className="btn-primary">
            Upload New Dataset
          </Link>
          <Link to="/verify" className="btn-secondary">
            Verify a Dataset
          </Link>
        </div>
      </div>
    </div>
  );
}
