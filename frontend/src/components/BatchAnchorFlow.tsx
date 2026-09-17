import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useWallet } from "../context/WalletContext";
import { uploadCsv } from "../api/datasets";
import { createBatch, submitBatch } from "../api/batches";
import CsvDropzone from "./CsvDropzone";
import SubmissionStepper from "./SubmissionStepper";
import AnomalyBadge from "./AnomalyBadge";
import AnomalyWarnings from "./AnomalyWarnings";
import TxExplorerLink from "./TxExplorerLink";
import { ProofPath } from "./MerkleProof";
import ErrorBanner from "./ErrorBanner";
import { apiErrorMessage } from "../utils/errors";
import type {
  BatchCreateResponse,
  BatchSubmitResponse,
  CsvPreview,
  DatasetCreateResponse,
  SubmissionStep,
} from "../types";

interface BatchMember {
  dataset: DatasetCreateResponse;
  fileName: string;
}

interface MembersProps {
  members: BatchMember[];
  onRemove?: (datasetId: string) => void;
}

function BatchMembers({ members, onRemove }: MembersProps) {
  if (members.length === 0) {
    return (
      <p className="text-sm text-gray-500">
        No datasets added yet. Upload a dataset below to start building a batch.
      </p>
    );
  }

  return (
    <ul className="divide-y divide-gray-100">
      {members.map(({ dataset, fileName }) => (
        <li key={dataset.dataset_id} className="py-3 flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-sm font-medium text-gray-700 truncate">{fileName}</p>
            <code className="text-xs font-mono text-gray-500 break-all">
              {dataset.dataset_hash}
            </code>
            <div className="mt-1">
              <AnomalyBadge score={dataset.anomaly_report.score} />
            </div>
          </div>
          {onRemove && (
            <button
              type="button"
              onClick={() => onRemove(dataset.dataset_id)}
              className="text-xs text-red-600 hover:underline shrink-0"
            >
              Remove
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}

/**
 * Batch anchoring flow: collect several datasets, commit them to one Merkle
 * root, and sign a single transaction that anchors the whole batch.
 *
 * Each dataset is uploaded and analyzed as it is added (so its hash and
 * anomaly report are real), but nothing is anchored until the root transaction
 * is signed — one on-chain entry instead of one per dataset.
 */
export default function BatchAnchorFlow() {
  const navigate = useNavigate();
  const { connected, publicKey, network, signTx, connect } = useWallet();

  const [step, setStep] = useState<SubmissionStep>("upload");
  const [members, setMembers] = useState<BatchMember[]>([]);
  const [pending, setPending] = useState<{
    file: File;
    preview: CsvPreview;
  } | null>(null);
  // Remount key so the dropzone clears its preview after a dataset is added.
  const [dropzoneKey, setDropzoneKey] = useState(0);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [batch, setBatch] = useState<BatchCreateResponse | null>(null);
  const [anchored, setAnchored] = useState<BatchSubmitResponse | null>(null);

  const handleFileSelected = useCallback((file: File, preview: CsvPreview) => {
    setPending({ file, preview });
    setError(null);
  }, []);

  const handleAddMember = useCallback(async () => {
    if (!pending || !publicKey) return;

    setProcessing(true);
    setError(null);
    try {
      const dataset = await uploadCsv(pending.file, publicKey);
      setMembers((prev) => [...prev, { dataset, fileName: pending.file.name }]);
      setPending(null);
      setDropzoneKey((key) => key + 1);
    } catch (err) {
      setError(apiErrorMessage(err, "Failed to process dataset"));
    } finally {
      setProcessing(false);
    }
  }, [pending, publicKey]);

  const handleRemoveMember = useCallback((datasetId: string) => {
    setMembers((prev) => prev.filter((member) => member.dataset.dataset_id !== datasetId));
  }, []);

  const handleCreateRoot = useCallback(async () => {
    if (!publicKey || members.length === 0) return;

    setProcessing(true);
    setError(null);
    try {
      const result = await createBatch(
        publicKey,
        members.map((member) => member.dataset.dataset_id),
      );
      setBatch(result);
      setStep("ai-report");
    } catch (err) {
      setError(apiErrorMessage(err, "Failed to build Merkle root"));
    } finally {
      setProcessing(false);
    }
  }, [publicKey, members]);

  const handleSignAndAnchor = useCallback(async () => {
    if (!batch) return;

    setProcessing(true);
    setError(null);
    try {
      const signedXdr = await signTx(batch.unsigned_transaction_xdr);
      const result = await submitBatch(batch.batch_id, signedXdr);
      setAnchored(result);
      setStep("confirmed");
    } catch (err) {
      const message = apiErrorMessage(err, "Batch submission failed");
      setStep("sign");
      setError(
        message.includes("User rejected")
          ? "Transaction was rejected in Freighter. Please try again."
          : message,
      );
    } finally {
      setProcessing(false);
    }
  }, [batch, signTx]);

  const handleReset = useCallback(() => {
    setStep("upload");
    setMembers([]);
    setPending(null);
    setDropzoneKey((key) => key + 1);
    setBatch(null);
    setAnchored(null);
    setError(null);
  }, []);

  const memberById = new Map(members.map((member) => [member.dataset.dataset_id, member]));

  return (
    <div className="space-y-6">
      <div className="mb-8">
        <SubmissionStepper currentStep={step} />
      </div>

      {error && <ErrorBanner message={error} />}

      {/* Step: Upload — collect datasets into the batch */}
      {step === "upload" && (
        <div className="space-y-6">
          <div className="card">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-semibold">Batch Contents</h2>
              <span className="text-sm text-gray-500">
                {members.length} dataset{members.length === 1 ? "" : "s"}
              </span>
            </div>
            <BatchMembers members={members} onRemove={handleRemoveMember} />
            {members.length > 0 && (
              <div className="mt-4 flex justify-end">
                <button
                  onClick={() => setStep("preview")}
                  className="btn-primary"
                  disabled={processing}
                >
                  Review Batch
                </button>
              </div>
            )}
          </div>

          <div className="card">
            <h2 className="text-lg font-semibold mb-4">Add a Dataset</h2>
            <CsvDropzone key={dropzoneKey} onFileSelected={handleFileSelected} />

            {pending ? (
              <div className="flex gap-3 justify-end mt-4">
                <button
                  onClick={() => {
                    setPending(null);
                    setDropzoneKey((key) => key + 1);
                  }}
                  className="btn-secondary"
                  disabled={processing}
                >
                  Cancel
                </button>
                <button
                  onClick={handleAddMember}
                  disabled={processing || !connected}
                  className="btn-primary inline-flex items-center gap-2"
                >
                  {processing ? (
                    <>
                      <span className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" />
                      Adding...
                    </>
                  ) : (
                    "Add to Batch"
                  )}
                </button>
              </div>
            ) : (
              <p className="text-xs text-gray-400 mt-3">
                Each dataset is hashed and checked for anomalies as you add it. Nothing is anchored
                until you sign the batch transaction.
              </p>
            )}

            {!connected && (
              <div className="text-center mt-3">
                <button onClick={connect} className="text-sm text-stellar hover:underline">
                  Connect your Freighter wallet to build a batch
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Step: Preview — confirm batch membership before committing */}
      {step === "preview" && (
        <div className="space-y-6">
          <div className="card">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-semibold">Batch Contents</h2>
              <span className="text-sm text-gray-500">
                {members.length} dataset{members.length === 1 ? "" : "s"}
              </span>
            </div>
            <BatchMembers members={members} />
            {members.length > 0 && (
              <div className="mt-4 bg-gray-50 rounded-lg p-3 text-sm text-gray-600">
                These datasets will be committed to a single Merkle root — one on-chain entry for
                the whole batch. Leaf order follows the order below, and each dataset keeps its own
                inclusion proof.
              </div>
            )}
          </div>

          <div className="flex flex-wrap gap-3 justify-end">
            <button onClick={handleReset} className="btn-secondary" disabled={processing}>
              Cancel
            </button>
            <button
              onClick={() => setStep("upload")}
              className="btn-secondary"
              disabled={processing}
            >
              Add Another Dataset
            </button>
            <button
              onClick={handleCreateRoot}
              disabled={processing || !connected || members.length === 0}
              className="btn-primary inline-flex items-center gap-2"
            >
              {processing ? (
                <>
                  <span className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" />
                  Building Merkle Root...
                </>
              ) : (
                "Create Merkle Root"
              )}
            </button>
          </div>
        </div>
      )}

      {/* Step: AI Report — review the root and its leaves */}
      {step === "ai-report" && batch && (
        <div className="space-y-6">
          <div className="card">
            <h2 className="text-lg font-semibold mb-4">Merkle Batch Summary</h2>

            <div className="mb-4">
              <span className="inline-flex items-center px-3 py-1 text-sm font-medium rounded-full bg-blue-100 text-blue-800">
                {batch.leaf_count} {batch.leaf_count === 1 ? "leaf" : "leaves"}
              </span>
            </div>

            <div className="bg-gray-50 rounded-lg p-3 mb-4">
              <p className="text-xs text-gray-500 mb-1">Merkle Root</p>
              <code className="text-sm font-mono text-gray-700 break-all">{batch.merkle_root}</code>
            </div>

            <p className="text-xs text-gray-500 mb-2">Committed datasets</p>
            <ul className="divide-y divide-gray-100">
              {batch.leaves.map((leaf) => {
                const member = memberById.get(leaf.dataset_id);
                return (
                  <li key={leaf.dataset_id} className="py-3 space-y-2">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-gray-700 truncate">
                          {member?.fileName ?? `${leaf.dataset_id.slice(0, 8)}...`}
                        </p>
                        <code className="text-xs font-mono text-gray-500 break-all">
                          {leaf.dataset_hash}
                        </code>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <AnomalyBadge score={leaf.anomaly_score} />
                        <span className="text-xs text-gray-500">Leaf {leaf.leaf_index}</span>
                      </div>
                    </div>
                    <AnomalyWarnings warnings={member?.dataset.anomaly_report.warnings ?? []} />
                  </li>
                );
              })}
            </ul>
          </div>

          <div className="flex gap-3 justify-end">
            <button onClick={handleReset} className="btn-secondary">
              Cancel
            </button>
            <button onClick={() => setStep("sign")} className="btn-primary">
              Continue to Sign
            </button>
          </div>
        </div>
      )}

      {/* Step: Sign — one signature anchors the whole batch */}
      {step === "sign" && batch && (
        <div className="space-y-6">
          <div className="card bg-blue-50 border border-blue-200">
            <p className="text-sm text-blue-800">
              Sign once to anchor all {batch.leaf_count} dataset
              {batch.leaf_count === 1 ? "" : "s"} in this batch. They share a single transaction.
            </p>
          </div>

          <div className="card space-y-3">
            <div className="flex justify-between text-sm gap-4">
              <span className="text-gray-500 shrink-0">Merkle Root</span>
              <code className="font-mono break-all text-right">
                {batch.merkle_root.slice(0, 16)}...
              </code>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">Datasets</span>
              <span className="font-medium">{batch.leaf_count}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">Network</span>
              <span className="font-medium capitalize">{network}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">Submitter</span>
              <code className="font-mono">{publicKey?.slice(0, 8)}...</code>
            </div>
          </div>

          <div className="flex gap-3 justify-end">
            <button onClick={handleReset} className="btn-secondary" disabled={processing}>
              Cancel
            </button>
            <button
              onClick={handleSignAndAnchor}
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
                "Sign & Anchor Batch"
              )}
            </button>
          </div>

          {!connected && (
            <div className="text-center">
              <button onClick={connect} className="text-sm text-stellar hover:underline">
                Connect your Freighter wallet to continue
              </button>
            </div>
          )}
        </div>
      )}

      {/* Step: Confirmed — show the root and every inclusion proof */}
      {step === "confirmed" && anchored && batch && (
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
            <h2 className="text-xl font-bold text-green-800 mb-2">Batch Anchored!</h2>
            <p className="text-green-700 text-sm mb-6">
              {batch.leaf_count} dataset{batch.leaf_count === 1 ? "" : "s"} are now provable against
              a single on-chain Merkle root.
            </p>

            <div className="max-w-sm mx-auto space-y-3 text-left">
              <div className="bg-white rounded-lg p-3 flex justify-between text-sm">
                <span className="text-gray-500">Status</span>
                <span className="font-semibold text-green-700 capitalize">{anchored.status}</span>
              </div>
              <div className="bg-white rounded-lg p-3 flex justify-between text-sm">
                <span className="text-gray-500">Ledger</span>
                <span className="font-mono">#{anchored.ledger_number}</span>
              </div>
              <div className="bg-white rounded-lg p-3 flex justify-between text-sm items-center gap-3">
                <span className="text-gray-500 shrink-0">Transaction</span>
                <TxExplorerLink txHash={anchored.stellar_tx_hash} network={network ?? "testnet"} />
              </div>
            </div>
          </div>

          <div className="card">
            <h2 className="text-sm font-semibold text-gray-700 mb-2">Merkle Root</h2>
            <code className="text-sm font-mono text-gray-700 break-all bg-gray-50 px-3 py-2 rounded block">
              {batch.merkle_root}
            </code>
          </div>

          <div className="space-y-4">
            <div>
              <h2 className="text-lg font-semibold">Inclusion Proofs</h2>
              <p className="text-sm text-gray-500 mt-1">
                Each dataset is proven by its leaf position and sibling path against the root above.
                Re-submit a dataset on the Verify page to re-check its proof.
              </p>
            </div>

            {batch.leaves.map((leaf) => {
              const member = memberById.get(leaf.dataset_id);
              return (
                <div key={leaf.dataset_id} className="card space-y-3">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-700 truncate">
                        {member?.fileName ?? `${leaf.dataset_id.slice(0, 8)}...`}
                      </p>
                      <code className="text-xs font-mono text-gray-500 break-all">
                        {leaf.dataset_hash}
                      </code>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <AnomalyBadge score={leaf.anomaly_score} />
                      <button
                        type="button"
                        onClick={() => navigate(`/verify?dataset_hash=${leaf.dataset_hash}`)}
                        className="text-xs text-stellar hover:underline"
                      >
                        Verify proof
                      </button>
                    </div>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 mb-1">Leaf Position</p>
                    <p className="text-sm font-mono text-gray-700">{leaf.leaf_index}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 mb-2">Sibling Path (bottom-up)</p>
                    <ProofPath siblings={leaf.merkle_proof} />
                  </div>
                </div>
              );
            })}
          </div>

          <div className="flex flex-wrap gap-3 justify-center">
            <button onClick={handleReset} className="btn-primary">
              Start a New Batch
            </button>
            <button onClick={() => navigate("/verify")} className="btn-secondary">
              Verify a Proof
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
