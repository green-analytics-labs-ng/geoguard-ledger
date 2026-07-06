/* eslint-disable react-refresh/only-export-components */
import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  type ReactNode,
} from "react";
import {
  isAllowed,
  isConnected as freighterIsConnected,
  getAddress,
  getNetwork,
  signTransaction as freighterSign,
  requestAccess,
} from "@stellar/freighter-api";

interface WalletState {
  connected: boolean;
  publicKey: string | null;
  network: "testnet" | "mainnet" | null;
  networkPassphrase: string;
  error: string | null;
}

interface WalletContextType extends WalletState {
  connect: () => Promise<void>;
  disconnect: () => void;
  signTx: (xdr: string) => Promise<string>;
}

const NETWORK_PASSPHRASES: Record<string, string> = {
  testnet: "Test SDF Network ; September 2015",
  mainnet: "Public Global Stellar Network ; September 2015",
};

const WalletContext = createContext<WalletContextType | null>(null);

export function WalletProvider({ children }: { children: ReactNode }) {
  const [wallet, setWallet] = useState<WalletState>({
    connected: false,
    publicKey: null,
    network: null,
    networkPassphrase: NETWORK_PASSPHRASES.testnet,
    error: null,
  });

  // On mount, check if Freighter is already connected
  useEffect(() => {
    (async () => {
      try {
        const allowedRes = await isAllowed();
        if (!allowedRes.isAllowed) return;

        const connectedRes = await freighterIsConnected();
        if (!connectedRes.isConnected) return;

        const addrRes = await getAddress();
        const networkRes = await getNetwork();
        const network =
          networkRes.network === "PUBLIC" ? "mainnet" : "testnet";

        setWallet({
          connected: true,
          publicKey: addrRes.address,
          network,
          networkPassphrase: networkRes.networkPassphrase,
          error: null,
        });
      } catch {
        // Freighter not installed or other error — stay disconnected
      }
    })();
  }, []);

  const connect = useCallback(async () => {
    setWallet((prev) => ({ ...prev, error: null }));

    try {
      const allowedRes = await isAllowed();
      if (!allowedRes.isAllowed) {
        await requestAccess();
      }

      const addrRes = await getAddress();
      const networkRes = await getNetwork();
      const network =
        networkRes.network === "PUBLIC" ? "mainnet" : "testnet";

      setWallet({
        connected: true,
        publicKey: addrRes.address,
        network,
        networkPassphrase: networkRes.networkPassphrase,
        error: null,
      });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to connect Freighter";
      setWallet((prev) => ({
        ...prev,
        connected: false,
        publicKey: null,
        network: null,
        error: message,
      }));
    }
  }, []);

  const disconnect = useCallback(() => {
    setWallet({
      connected: false,
      publicKey: null,
      network: null,
      networkPassphrase: NETWORK_PASSPHRASES.testnet,
      error: null,
    });
  }, []);

  const signTx = useCallback(
    async (xdr: string): Promise<string> => {
      const signed = await freighterSign(xdr, {
        networkPassphrase: wallet.networkPassphrase,
      });
      if (signed.error) {
        throw new Error(
          signed.error.message || "Failed to sign transaction",
        );
      }
      return signed.signedTxXdr;
    },
    [wallet.networkPassphrase],
  );

  return (
    <WalletContext.Provider
      value={{
        ...wallet,
        connect,
        disconnect,
        signTx,
      }}
    >
      {children}
    </WalletContext.Provider>
  );
}

export function useWallet(): WalletContextType {
  const ctx = useContext(WalletContext);
  if (!ctx) throw new Error("useWallet must be used within WalletProvider");
  return ctx;
}
