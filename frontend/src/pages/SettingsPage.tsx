import { useState } from "react";
import { useWallet } from "../context/WalletContext";
import WalletConnector from "../components/WalletConnector";
import { clearApiKey, hasApiKey, setApiKey } from "../api/apiKey";

export default function SettingsPage() {
  const { connected, publicKey, network, error, disconnect } = useWallet();

  // The input is write-only in the UI: the stored key is never read back into
  // the field, only its presence is reflected.
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [apiKeyConfigured, setApiKeyConfigured] = useState(hasApiKey);
  const [saved, setSaved] = useState(false);

  function handleSaveApiKey() {
    setApiKey(apiKeyInput);
    setApiKeyInput("");
    setApiKeyConfigured(hasApiKey());
    setSaved(true);
  }

  function handleClearApiKey() {
    clearApiKey();
    setApiKeyInput("");
    setApiKeyConfigured(false);
    setSaved(false);
  }

  return (
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

      {/* API Access Section */}
      <div className="card mb-6">
        <h2 className="text-lg font-semibold mb-4">API Access</h2>
        <div className="space-y-3">
          <p className="text-sm text-gray-600">
            Uploading and anchoring require an API key when the backend has{" "}
            <code className="text-xs bg-gray-100 px-1 py-0.5 rounded">API_KEYS</code> configured.
            The key is stored in this browser and sent as the{" "}
            <code className="text-xs bg-gray-100 px-1 py-0.5 rounded">X-API-Key</code> header on
            upload and anchoring requests. Verification stays public and never carries it.
          </p>
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <label htmlFor="api-key" className="block text-xs text-gray-500 mb-1">
                API Key
              </label>
              <input
                id="api-key"
                type="password"
                value={apiKeyInput}
                onChange={(event) => {
                  setApiKeyInput(event.target.value);
                  setSaved(false);
                }}
                placeholder={apiKeyConfigured ? "•••••••• (saved)" : "Paste your API key"}
                autoComplete="off"
                className="input-field font-mono text-sm"
              />
            </div>
            <button onClick={handleSaveApiKey} className="btn-primary">
              Save
            </button>
            {apiKeyConfigured && (
              <button onClick={handleClearApiKey} className="btn-secondary">
                Clear
              </button>
            )}
          </div>
          {saved && <p className="text-sm text-green-700">API key saved.</p>}
          {apiKeyConfigured && !saved && (
            <p className="text-sm text-gray-500">A key is configured for this browser.</p>
          )}
        </div>
      </div>

      {/* Network Section */}
      <div className="card mb-6">
        <h2 className="text-lg font-semibold mb-4">Network</h2>
        <div className="space-y-3">
          <p className="text-sm text-gray-600">
            Currently connected to the Stellar network. To switch networks, change the network in
            your Freighter wallet extension.
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
              <div className="text-xs mt-1 opacity-70">For development & testing</div>
            </div>
            <div
              className={`flex-1 px-4 py-3 rounded-lg border text-sm font-medium ${
                network === "mainnet"
                  ? "bg-blue-50 border-blue-300 text-blue-800"
                  : "bg-white border-gray-200 text-gray-400"
              }`}
            >
              <div className="font-semibold">Mainnet</div>
              <div className="text-xs mt-1 opacity-70">Production (requires real XLM)</div>
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
            <strong>GeoGuard Ledger</strong> v0.3.0
          </p>
          <p>
            An open-source research integrity system for geochemical data anchoring on the Stellar
            blockchain.
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
  );
}
