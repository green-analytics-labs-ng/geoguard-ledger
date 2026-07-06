interface Props {
  txHash: string;
  network?: "testnet" | "mainnet";
  label?: string;
  className?: string;
}

export default function TxExplorerLink({ txHash, network = "testnet", label, className = "" }: Props) {
  const base =
    network === "mainnet"
      ? "https://stellar.expert/explorer/public"
      : "https://stellar.expert/explorer/testnet";
  return (
    <a
      href={`${base}/tx/${txHash}`}
      target="_blank"
      rel="noopener noreferrer"
      className={`inline-flex items-center gap-1 text-stellar hover:text-blue-700 transition-colors ${className}`}
    >
      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
        />
      </svg>
      {label || `${txHash.slice(0, 8)}...${txHash.slice(-8)}`}
    </a>
  );
}
