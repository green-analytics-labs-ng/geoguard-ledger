import { inclusionVerdict, isInclusionVerified } from "../utils/merkle";

interface ProofPathProps {
  siblings: string[];
}

/**
 * The bottom-up sibling hashes that prove one leaf belongs to a Merkle root.
 * An empty path is meaningful: a single-leaf batch's root is that leaf's hash.
 */
export function ProofPath({ siblings }: ProofPathProps) {
  if (siblings.length === 0) {
    return (
      <p className="text-sm text-gray-500">
        No sibling hashes — this batch has a single leaf, so the root is the dataset&apos;s own
        hash.
      </p>
    );
  }

  return (
    <ol className="space-y-1">
      {siblings.map((sibling, i) => (
        <li key={`${i}-${sibling}`} className="flex gap-2">
          <span className="text-xs text-gray-400 font-mono w-6 shrink-0 pt-0.5">{i + 1}</span>
          <code className="text-xs font-mono text-gray-600 break-all">{sibling}</code>
        </li>
      ))}
    </ol>
  );
}

interface VerdictBadgeProps {
  verifiedLocally?: boolean;
  verifiedOnChain?: boolean | null;
}

/** Colour-coded badge for how an inclusion proof was validated. */
export function InclusionVerdictBadge({ verifiedLocally, verifiedOnChain }: VerdictBadgeProps) {
  const verdict = inclusionVerdict(verifiedLocally, verifiedOnChain);

  if (verdict === "on-chain") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full bg-green-100 text-green-800 border border-green-200">
        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
        </svg>
        Verified on-chain
      </span>
    );
  }

  if (verdict === "local") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full bg-blue-100 text-blue-800 border border-blue-200">
        Verified locally — on-chain check unavailable
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full bg-red-100 text-red-800 border border-red-200">
      Not verified
    </span>
  );
}

interface Props {
  root: string;
  leafIndex: number;
  proof: string[];
  batchId?: string | null;
  verifiedLocally?: boolean;
  verifiedOnChain?: boolean | null;
  /**
   * Whether to show how the proof was validated. Set false where the proof is
   * presented as a claim that has not been checked yet — the badge would
   * otherwise read "Not verified" and imply the proof itself failed.
   */
  showVerdict?: boolean;
}

/**
 * Shows how one dataset is proven to belong to an anchored batch: the Merkle
 * root, the dataset's leaf position, and the sibling path needed to recompute
 * the root — everything a third party needs to check the claim independently.
 */
export default function MerkleProof({
  root,
  leafIndex,
  proof,
  batchId,
  verifiedLocally,
  verifiedOnChain,
  showVerdict = true,
}: Props) {
  const verdict = inclusionVerdict(verifiedLocally, verifiedOnChain);
  const verified = showVerdict && isInclusionVerified(verdict);

  return (
    <div
      className={`border rounded-lg p-4 space-y-4 ${
        showVerdict && !verified ? "border-red-200 bg-red-50" : "border-gray-200 bg-white"
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-gray-700">Merkle Inclusion Proof</h3>
        {showVerdict && (
          <InclusionVerdictBadge
            verifiedLocally={verifiedLocally}
            verifiedOnChain={verifiedOnChain}
          />
        )}
      </div>

      <div>
        <p className="text-xs text-gray-500 mb-1">Batch Root (SHA-256)</p>
        <code className="text-sm font-mono text-gray-700 break-all bg-gray-50 px-3 py-2 rounded block">
          {root}
        </code>
      </div>

      <div className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <p className="text-xs text-gray-500 mb-1">Leaf Position</p>
          <p className="font-mono text-gray-700">{leafIndex}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500 mb-1">Proof Length</p>
          <p className="font-mono text-gray-700">
            {proof.length} sibling{proof.length === 1 ? "" : "s"}
          </p>
        </div>
      </div>

      <div>
        <p className="text-xs text-gray-500 mb-2">Sibling Path (bottom-up)</p>
        <ProofPath siblings={proof} />
      </div>

      {batchId && (
        <div>
          <p className="text-xs text-gray-500 mb-1">Batch</p>
          <code className="text-xs font-mono text-gray-500 break-all">{batchId}</code>
        </div>
      )}
    </div>
  );
}
