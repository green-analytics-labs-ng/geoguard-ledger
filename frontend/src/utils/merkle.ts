/**
 * Helpers for interpreting Merkle batch inclusion results.
 *
 * A dataset in a batch is anchored by the batch's root rather than by its own
 * on-chain record, so its integrity is proven by an inclusion proof instead of
 * a direct `verify_integrity` lookup.
 */

import type { DatasetResponse } from "../types";

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

/** The fields that mark a dataset as committed to by a batch Merkle root. */
export type BatchMembershipFields = Pick<
  DatasetResponse,
  "batch_id" | "merkle_root" | "leaf_index" | "merkle_proof"
>;

/** A dataset's membership in an anchored batch, with everything needed to
 * recompute the root from its leaf. */
export interface BatchMembership {
  batchId: string;
  root: string;
  leafIndex: number;
  proof: string[];
}

/**
 * Describe a dataset's batch membership, or `null` when it was anchored under
 * its own hash.
 *
 * Membership is decided by `batch_id`, `merkle_root` and `leaf_index` rather
 * than by the proof path: a single-leaf batch legitimately has an empty path,
 * because its root is the leaf's own hash. A dataset that has a batch assigned
 * but no proof recorded yet is still reported as a member.
 */
export function batchMembership(dataset: BatchMembershipFields): BatchMembership | null {
  const { batch_id, merkle_root, leaf_index, merkle_proof } = dataset;

  if (!batch_id || merkle_root == null || leaf_index == null) {
    return null;
  }

  return {
    batchId: batch_id,
    root: merkle_root,
    leafIndex: leaf_index,
    proof: merkle_proof ?? [],
  };
}
