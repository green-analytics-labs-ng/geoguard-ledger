import { useNavigate } from "react-router-dom";
import { useWallet } from "../context/WalletContext";
import WalletConnector from "../components/WalletConnector";

export default function SettingsPage() {
  const navigate = useNavigate();
  const { connected, publicKey, network, error, disconnect } = useWallet();

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
        </div>
      </nav>

      <div className="max-w-3xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold text-stellar mb-6">Settings</h1>

        {/* Wallet Section */}
        <div className="card mb-6">
          <h2 className="text-lg font-semibold mb-4">Wallet</h2>
          {connected && publicKey ? (
            <div className="space-y-3">
              <div className="bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-500 mb-1">Connected Address</p>
                <p className="text-sm font-mono break-all">{publicKey}</p>
              </div>
              <button
                onClick={disconnect}
                className="text-sm text-red-600 hover:text-red-800 transition-colors"
              >
                Disconnect Wallet
              </button>
            </div>
          ) : (
            <WalletConnector />
          )}
        </div>

        {/* Network Section */}
        <div className="card mb-6">
          <h2 className="text-lg font-semibold mb-4">Network</h2>
          <div className="space-y-3">
            <p className="text-sm text-gray-600">
              Currently connected to the Stellar network. To switch networks,
              change the network in your Freighter wallet extension.
            </p>
            <div className="flex gap-3">
              <div
                className={`flex-1 px-4 py-3 rounded-lg border text-sm font-medium ${
                  network === "testnet"
                    ? "bg-yellow-50 border-yellow-300 text-yellow-800"
                    : "bg-white border-gray-200 text-gray-400"
                }`}
              >
                <div className="font-semibold">Testnet</div>
                <div className="text-xs mt-1 opacity-70">
                  For development & testing
                </div>
              </div>
              <div
                className={`flex-1 px-4 py-3 rounded-lg border text-sm font-medium ${
                  network === "mainnet"
                    ? "bg-blue-50 border-blue-300 text-blue-800"
                    : "bg-white border-gray-200 text-gray-400"
                }`}
              >
                <div className="font-semibold">Mainnet</div>
                <div className="text-xs mt-1 opacity-70">
                  Production (requires real XLM)
                </div>
              </div>
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
          </div>
        </div>

        {/* About Section */}
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">About</h2>
          <div className="space-y-2 text-sm text-gray-600">
            <p>
              <strong>GeoGuard Ledger</strong> v0.2.0
            </p>
            <p>
              An open-source research integrity system for geochemical data
              anchoring on the Stellar blockchain.
            </p>
            <p>
              Built by{" "}
              <a
                href="https://github.com/green-analytics-labs"
                target="_blank"
                rel="noopener noreferrer"
                className="text-stellar hover:underline"
              >
                Green Analytics Labs
              </a>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
