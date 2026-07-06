import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useWallet } from "../context/WalletContext";
import { uploadCsv, submitDataset } from "../api/datasets";
import CsvDropzone from "../components/CsvDropzone";
import SubmissionStepper from "../components/SubmissionStepper";
import AnomalyBadge from "../components/AnomalyBadge";
import TxExplorerLink from "../components/TxExplorerLink";
import WalletConnector from "../components/WalletConnector";
import type { CsvPreview, SubmissionStep, DatasetCreateResponse, SubmitResponse } from "../types";

export default function UploadPage() {
  const navigate = useNavigate();
  const { connected, publicKey, network, signTx, connect } =
    useWallet();

  const [step, setStep] = useState<SubmissionStep>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<CsvPreview | null>(null);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Dataset creation response from backend
  const [createResponse, setCreateResponse] =
    useState<DatasetCreateResponse | null>(null);

  // Submit response after anchoring
  const [submitResponse, setSubmitResponse] =
    useState<SubmitResponse | null>(null);

  const handleFileSelected = useCallback(
    (selectedFile: File, csvPreview: CsvPreview) => {
      setFile(selectedFile);
      setPreview(csvPreview);
      setStep("preview");
      setError(null);
    },
    [],
  );

  const handleSubmitToBackend = useCallback(async () => {
    if (!file || !publicKey) return;

    setProcessing(true);
    setError(null);
    try {
      const result = await uploadCsv(file, publicKey);
      setCreateResponse(result);
      setStep("ai-report");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to process dataset",
      );
    } finally {
      setProcessing(false);
    }
  }, [file, publicKey]);

  const handleSignAndSubmit = useCallback(async () => {
    if (!createResponse) return;

    setProcessing(true);
    setError(null);
    try {
      // Sign the transaction via Freighter
      const signedXdr = await signTx(createResponse.unsigned_transaction_xdr);
      setStep("confirmed");

      // Submit the signed transaction to the backend
      const result = await submitDataset(
        createResponse.dataset_id,
        signedXdr,
      );
      setSubmitResponse(result);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Submission failed";
      if (message.includes("User rejected")) {
        setStep("sign");
        setError("Transaction was rejected in Freighter. Please try again.");
      } else {
        setStep("sign");
        setError(message);
      }
    } finally {
      setProcessing(false);
    }
  }, [createResponse, signTx]);

  const handleReset = useCallback(() => {
    setStep("upload");
    setFile(null);
    setPreview(null);
    setCreateResponse(null);
    setSubmitResponse(null);
    setError(null);
  }, []);

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
          <WalletConnector compact />
        </div>
      </nav>

      <div className="max-w-3xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold text-stellar mb-2">
          Upload Dataset
        </h1>
        <p className="text-sm text-gray-500 mb-8">
          Upload a geochemical CSV dataset. The data will be hashed, analyzed
          for anomalies, and anchored to the Stellar blockchain.
        </p>

        {/* Stepper */}
        <div className="mb-8">
          <SubmissionStepper currentStep={step} />
        </div>

        {/* Error */}
        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 text-red-700 rounded-lg p-4 text-sm">
            {error}
          </div>
        )}

        {/* Step: Upload */}
        {step === "upload" && (
          <div className="card">
            <CsvDropzone onFileSelected={handleFileSelected} />
          </div>
        )}

        {/* Step: Preview */}
        {step === "preview" && preview && (
          <div className="space-y-6">
            <div className="card bg-yellow-50 border border-yellow-200">
              <p className="text-sm text-yellow-800">
                Review the data preview below. When you're ready, we'll hash
                the dataset and run AI anomaly detection.
              </p>
            </div>
            <div className="card">
              <CsvDropzone onFileSelected={handleFileSelected} />
            </div>
            <div className="flex gap-3 justify-end">
              <button
                onClick={handleReset}
                className="btn-secondary"
                disabled={processing}
              >
                Cancel
              </button>
              <button
                onClick={handleSubmitToBackend}
                disabled={processing}
                className="btn-primary inline-flex items-center gap-2"
              >
                {processing ? (
                  <>
                    <span className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" />
                    Processing...
                  </>
                ) : (
                  "Process & Detect Anomalies"
                )}
              </button>
            </div>
          </div>
        )}

        {/* Step: AI Report */}
        {step === "ai-report" && createResponse && (
          <div className="space-y-6">
            <div className="card">
              <h2 className="text-lg font-semibold mb-4">
                AI Anomaly Report
              </h2>
              <div className="flex items-center gap-3 mb-4">
                <AnomalyBadge
                  score={createResponse.anomaly_report.score}
                  size="md"
                  showLabel
                />
                <span className="text-sm text-gray-500">
                  {createResponse.anomaly_report.summary}
                </span>
              </div>
              {createResponse.anomaly_report.flags.length > 0 && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
                  <strong>{createResponse.anomaly_report.flags.length} row(s)</strong> flagged as anomalous.
                </div>
              )}
              <div className="mt-4 bg-gray-50 rounded-lg p-3">
                <p className="text-xs text-gray-500 mb-1">Dataset Hash</p>
                <code className="text-sm font-mono text-gray-700 break-all">
                  {createResponse.dataset_hash}
                </code>
              </div>
            </div>

            <div className="flex gap-3 justify-end">
              <button onClick={handleReset} className="btn-secondary">
                Cancel
              </button>
              <button
                onClick={() => setStep("sign")}
                className="btn-primary"
              >
                Continue to Sign
              </button>
            </div>
          </div>
        )}

        {/* Step: Sign */}
        {step === "sign" && (
          <div className="space-y-6">
            <div className="card bg-blue-50 border border-blue-200">
              <p className="text-sm text-blue-800">
                Review the transaction details and sign with your Freighter
                wallet to anchor this proof on the Stellar network.
              </p>
            </div>
            <div className="card space-y-3">
              {createResponse && (
                <>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Dataset Hash</span>
                    <code className="font-mono">
                      {createResponse.dataset_hash.slice(0, 16)}...
                    </code>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Anomaly Score</span>
                    <AnomalyBadge
                      score={createResponse.anomaly_report.score}
                    />
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Network</span>
                    <span className="font-medium capitalize">{network}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Submitter</span>
                    <code className="font-mono">
                      {publicKey?.slice(0, 8)}...
                    </code>
                  </div>
                </>
              )}
            </div>
            <div className="flex gap-3 justify-end">
              <button
                onClick={handleReset}
                className="btn-secondary"
                disabled={processing}
              >
                Cancel
              </button>
              <button
                onClick={handleSignAndSubmit}
                disabled={processing || !connected}
                className="btn-primary inline-flex items-center gap-2"
              >
                {processing ? (
                  <>
                    <span className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" />
                    Signing & Anchoring...
                  </>
                ) : !connected ? (
                  "Connect Wallet First"
                ) : (
                  "Sign & Anchor to Stellar"
                )}
              </button>
            </div>
            {!connected && (
              <div className="text-center">
                <button
                  onClick={connect}
                  className="text-sm text-stellar hover:underline"
                >
                  Connect your Freighter wallet to continue
                </button>
              </div>
            )}
          </div>
        )}

        {/* Step: Confirmed */}
        {step === "confirmed" && submitResponse && (
          <div className="space-y-6">
            <div className="bg-green-50 border border-green-200 rounded-lg p-6 text-center">
              <svg
                className="mx-auto w-12 h-12 text-green-500 mb-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <h2 className="text-xl font-bold text-green-800 mb-2">
                Dataset Anchored!
              </h2>
              <p className="text-green-700 text-sm mb-6">
                Your dataset integrity proof is now on the Stellar blockchain.
              </p>

              <div className="max-w-sm mx-auto space-y-3 text-left">
                <div className="bg-white rounded-lg p-3 flex justify-between text-sm">
                  <span className="text-gray-500">Status</span>
                  <span className="font-semibold text-green-700 capitalize">
                    {submitResponse.status}
                  </span>
                </div>
                <div className="bg-white rounded-lg p-3 flex justify-between text-sm">
                  <span className="text-gray-500">Ledger</span>
                  <span className="font-mono">
                    #{submitResponse.ledger_number}
                  </span>
                </div>
                <div className="bg-white rounded-lg p-3 flex justify-between text-sm items-center">
                  <span className="text-gray-500">Transaction</span>
                  <TxExplorerLink
                    txHash={submitResponse.stellar_tx_hash}
                    network={network ?? "testnet"}
                  />
                </div>
              </div>
            </div>

            <div className="flex gap-3 justify-center">
              <button
                onClick={handleReset}
                className="btn-primary"
              >
                Upload Another Dataset
              </button>
              <button
                onClick={() =>
                  navigate(`/datasets/${submitResponse.dataset_id}`)
                }
                className="btn-secondary"
              >
                View Details
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
