import { useWallet } from "../context/WalletContext";

interface Props {
  compact?: boolean;
}

export default function WalletConnector({ compact }: Props) {
  const { connected, publicKey, network, error, connect, disconnect } =
    useWallet();

  if (connected && publicKey) {
    return (
      <div
        className={`flex items-center gap-3 ${compact ? "" : "p-4 bg-white border border-gray-200 rounded-lg"}`}
      >
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-green-500" />
          <span className="text-sm font-mono">
            {publicKey.slice(0, 6)}...{publicKey.slice(-4)}
          </span>
        </div>
        <span
          className={`text-xs px-2 py-0.5 rounded-full ${
            network === "testnet"
              ? "bg-yellow-100 text-yellow-800"
              : "bg-blue-100 text-blue-800"
          }`}
        >
          {network}
        </span>
        <button
          onClick={disconnect}
          className="ml-auto text-sm text-gray-500 hover:text-red-600 transition-colors"
        >
          Disconnect
        </button>
      </div>
    );
  }

  return (
    <div className={compact ? "" : "space-y-3"}>
      {!compact && (
        <p className="text-sm text-gray-600">
          Connect your Freighter wallet to get started.
        </p>
      )}
      <button
        onClick={connect}
        className={`
          inline-flex items-center gap-2 px-4 py-2 rounded-lg font-medium
          transition-all duration-200
          bg-stellar text-white hover:bg-blue-700
          active:scale-95
        `}
      >
        <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z" />
        </svg>
        Connect Freighter
      </button>
      {error && (
        <p className="text-sm text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}
