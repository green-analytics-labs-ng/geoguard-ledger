import { Link } from "react-router-dom";

export default function DashboardPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
          <h1 className="text-xl font-bold text-stellar">GeoGuard Ledger</h1>
          <nav className="flex gap-4 text-sm">
            <Link to="/" className="text-gray-600 hover:text-stellar transition-colors">Dashboard</Link>
            <Link to="/upload" className="text-gray-600 hover:text-stellar transition-colors">Upload</Link>
            <Link to="/datasets" className="text-gray-600 hover:text-stellar transition-colors">Datasets</Link>
            <Link to="/verify" className="text-gray-600 hover:text-stellar transition-colors">Verify</Link>
            <Link to="/settings" className="text-gray-600 hover:text-stellar transition-colors">Settings</Link>
          </nav>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
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
            <Link to="/upload" className="btn-primary">Upload New Dataset</Link>
            <Link to="/verify" className="btn-secondary">Verify a Dataset</Link>
          </div>
        </div>
      </main>
    </div>
  );
}
