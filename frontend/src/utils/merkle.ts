/**
 * Helpers for interpreting Merkle batch inclusion results.
 *
 * A dataset in a batch is anchored by the batch's root rather than by its own
 * on-chain record, so its integrity is proven by an inclusion proof instead of
 * a direct `verify_integrity` lookup.
 */

export type InclusionVerdict = "on-chain" | "local" | "unverified";

/**
 * Grade an inclusion proof from the backend's two verdicts.
 *
 * An explicit on-chain `false` is treated as authoritative — it means the
 * contract rejected the proof, or the batch root is not anchored (yet) — so it
 * outranks a local pass, which only reflects the backend's own re-computation.
 */
export function inclusionVerdict(
  verifiedLocally: boolean | undefined,
  verifiedOnChain: boolean | null | undefined,
): InclusionVerdict {
  if (verifiedOnChain === true) return "on-chain";
  if (verifiedOnChain === false) return "unverified";
  return verifiedLocally ? "local" : "unverified";
}

/** True when a verdict means the dataset is proven to be part of the batch. */
export function isInclusionVerified(verdict: InclusionVerdict): boolean {
  return verdict === "on-chain" || verdict === "local";
}
