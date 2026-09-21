import { useWallet } from "../context/WalletContext";
import { useContractNetworkPassphrase } from "../hooks/useContractNetworkPassphrase";
import { networkFromPassphrase } from "../utils/stellar";

/**
 * Warns when the connected wallet signs for a different Stellar network than
 * the deployment anchors to.
 *
 * The anchor transaction is built by the backend against its own network
 * passphrase and then signed by Freighter against the wallet's. When the two
 * differ the signature is simply invalid for the network it is submitted to —
 * the failure is rejected rather than explained, and the natural assumption is
 * that the data or the contract is at fault. Nothing else in the app can see
 * both halves, so this is where the comparison has to happen.
 *
 * Silent in the three states where it would be guessing: no wallet connected,
 * no answer from `/health`, or the wallet has not reported its passphrase yet.
 */
export default function NetworkMismatchBanner() {
  const { connected, networkPassphrase } = useWallet();
  const contractPassphrase = useContractNetworkPassphrase(connected);

  if (!connected || !networkPassphrase || !contractPassphrase) return null;
  if (networkPassphrase === contractPassphrase) return null;

  const walletNetwork = networkFromPassphrase(networkPassphrase);
  const contractNetwork = networkFromPassphrase(contractPassphrase);

  return (
    <div role="alert" className="bg-yellow-50 border-b border-yellow-200">
      <p className="max-w-7xl mx-auto px-4 py-2 text-sm text-center text-yellow-900">
        Your Freighter wallet is signing for {walletNetwork ?? "an unrecognized network"}, but this
        deployment anchors to {contractNetwork ?? "a different network"}. A transaction signed for
        the wrong network is rejected by the contract, so switch networks in Freighter and reconnect
        before anchoring.
      </p>
    </div>
  );
}
