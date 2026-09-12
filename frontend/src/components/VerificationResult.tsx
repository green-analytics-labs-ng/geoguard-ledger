import type { VerifyResult } from "../types";
import AnomalyBadge from "./AnomalyBadge";
import MerkleProof from "./MerkleProof";
import { inclusionVerdict, isInclusionVerified } from "../utils/merkle";

interface Props {
  result: VerifyResult;
}

export default function VerificationResult({ result }: Props) {
  const { match, on_chain_record, re_computed_hash, inclusion } = result;

  // A dataset anchored in a batch has no standalone on-chain record, so its
  // integrity is proven by its inclusion proof instead of by `match`.
  const batchVerified =
    inclusion !== undefined &&
    inclusion !== null &&
    isInclusionVerified(
      inclusionVerdict(inclusion.verified_locally, inclusion.verified_on_chain),
    );
  const verified = match || batchVerified;

  let headline: string;
  let description: string;

  if (match) {
    headline = "Dataset Verified";
    description =
      "The dataset hash matches a record on the Stellar blockchain.";
  } else if (batchVerified) {
    headline = "Included in Anchored Batch";
    description =
      "This hash has no standalone record, but a Merkle inclusion proof against an anchored batch root verifies it.";
  } else {
    headline = "Not Verified";
    description = inclusion
      ? "The batch inclusion proof did not verify. The dataset may have been altered, or its batch root is not anchored yet."
      : "This dataset hash was not found on the Stellar blockchain.";
  }

  return (
    <div className="space-y-4">
      {/* Match status banner */}
      <div
        className={`rounded-lg p-4 flex items-center gap-3 ${
          verified
            ? "bg-green-50 border border-green-200"
            : "bg-red-50 border border-red-200"
        }`}
      >
        {verified ? (
          <svg
            className="w-6 h-6 text-green-600 shrink-0"
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
        ) : (
          <svg
            className="w-6 h-6 text-red-600 shrink-0"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        )}
        <div>
          <p
            className={`font-semibold ${verified ? "text-green-800" : "text-red-800"}`}
          >
            {headline}
          </p>
          <p
            className={`text-sm ${verified ? "text-green-700" : "text-red-700"}`}
          >
            {description}
          </p>
        </div>
      </div>

      {/* Re-computed hash */}
      {re_computed_hash && (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
          <p className="text-xs text-gray-500 mb-1">Re-computed Hash</p>
          <code className="text-sm font-mono text-gray-700 break-all">
            {re_computed_hash}
          </code>
        </div>
      )}

      {/* Batch inclusion proof */}
      {inclusion && (
        <MerkleProof
          root={inclusion.root}
          leafIndex={inclusion.leaf_index}
          proof={inclusion.proof}
          batchId={inclusion.batch_id}
          verifiedLocally={inclusion.verified_locally}
          verifiedOnChain={inclusion.verified_on_chain}
        />
      )}

      {/* On-chain record */}
      {on_chain_record && (
        <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-3">
          <h3 className="text-sm font-semibold text-gray-700">
            On-Chain Record
          </h3>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <p className="text-xs text-gray-500">Anomaly Score</p>
              <AnomalyBadge
                score={(on_chain_record.anomaly_score ?? 0) / 10000}
                size="md"
              />
            </div>
            <div>
              <p className="text-xs text-gray-500">Model</p>
              <p className="font-mono text-gray-700">
                {on_chain_record.model_version}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Submitter</p>
              <p className="font-mono text-gray-700 text-xs break-all">
                {on_chain_record.submitter}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Timestamp</p>
              <p className="text-gray-700">
                {new Date(
                  (on_chain_record.timestamp ?? 0) * 1000,
                ).toLocaleString()}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Static empty-state component for before verification is run
export function VerificationResultEmpty() {
  return (
    <div className="text-center py-12">
      <svg
        className="mx-auto h-12 w-12 text-gray-300 mb-4"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.5}
          d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
        />
      </svg>
      <p className="text-gray-500">
        Upload a data file or paste a hash to verify its integrity proof on-chain.
      </p>
    </div>
  );
}
