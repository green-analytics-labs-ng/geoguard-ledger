import type { BatchMembership } from "../utils/merkle";

interface Props {
  membership: BatchMembership;
}

/**
 * Marks a dataset as committed to by a batch Merkle root rather than anchored
 * under its own hash.
 *
 * The batch id and root go in the title text so the badge stays narrow enough
 * for a table cell while still being inspectable without leaving the page.
 */
export default function BatchBadge({ membership }: Props) {
  const { batchId, root, leafIndex } = membership;

  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full bg-violet-100 text-violet-800 border border-violet-200"
      title={`Batched — leaf ${leafIndex} of Merkle root ${root} (batch ${batchId})`}
    >
      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M12 3l8 4.5-8 4.5-8-4.5 8-4.5z"
        />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 12l8 4.5 8-4.5" />
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M4 16.5l8 4.5 8-4.5"
        />
      </svg>
      Batch &middot; leaf {leafIndex}
    </span>
  );
}
