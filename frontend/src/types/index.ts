/** Shared TypeScript types for the frontend. */

export interface AnchorRecord {
  dataset_hash: string;
  anomaly_score: number;
  model_version: string;
  timestamp: number;
  submitter: string;
}

export interface AnomalyReport {
  score: number;
  flags: number[];
  model_version: string;
  summary: string;
  /**
   * Geochemical plausibility findings from deterministic range checks, e.g.
   * `"[ERROR] pH: 1 value(s) outside the plausible range 0 to 14 (rows 4)"`.
   * Present even when the dataset is too small for the statistical model.
   */
  warnings?: string[];
}

export interface DatasetCreateResponse {
  dataset_id: string;
  dataset_hash: string;
  anomaly_report: AnomalyReport;
  unsigned_transaction_xdr: string;
  created_at: string;
}

export interface SubmitResponse {
  dataset_id: string;
  status: "anchored" | "failed";
  stellar_tx_hash: string;
  ledger_number: number;
  explorer_url: string;
  anchored_at: string;
}

export interface DatasetResponse {
  dataset_id: string;
  dataset_hash: string;
  status: "pending" | "anchored" | "failed";
  anomaly_score: number;
  anomaly_report?: AnomalyReport;
  stellar_tx_hash?: string;
  explorer_url?: string;
  /** Set when the dataset was anchored as part of a Merkle batch. */
  batch_id?: string | null;
  merkle_root?: string | null;
  leaf_index?: number | null;
  merkle_proof?: string[] | null;
  created_at: string;
  anchored_at?: string;
}

/**
 * How a dataset is proven inside its batch's Merkle root.
 *
 * `verified_locally` is the backend's own proof check, while
 * `verified_on_chain` is the contract's `verify_inclusion` verdict — `null`
 * when the on-chain check could not be evaluated.
 */
export interface InclusionProof {
  root: string;
  leaf_index: number;
  proof: string[];
  batch_id: string;
  verified_locally: boolean;
  verified_on_chain: boolean | null;
}

export interface VerifyResult {
  match: boolean;
  on_chain_record: AnchorRecord | null;
  local_record: DatasetResponse | null;
  re_computed_hash?: string;
  /** Present for batched datasets, `null` otherwise. */
  inclusion?: InclusionProof | null;
}

/** One dataset committed to by a batch Merkle root. */
export interface BatchLeaf {
  dataset_id: string;
  dataset_hash: string;
  leaf_index: number;
  merkle_proof: string[];
  anomaly_score: number;
}

export interface BatchCreateResponse {
  batch_id: string;
  merkle_root: string;
  leaf_count: number;
  unsigned_transaction_xdr: string;
  leaves: BatchLeaf[];
  created_at: string;
}

export interface BatchSubmitResponse {
  batch_id: string;
  status: "anchored" | "failed";
  stellar_tx_hash: string;
  ledger_number: number;
  explorer_url: string;
  anchored_at: string;
}

export interface BatchResponse {
  batch_id: string;
  merkle_root: string;
  leaf_count: number;
  submitter_address: string;
  status: "pending" | "anchored" | "failed";
  stellar_tx_hash?: string | null;
  explorer_url?: string | null;
  created_at: string;
  anchored_at?: string | null;
}

export interface CsvPreview {
  headers: string[];
  rows: string[][];
  totalRows: number;
}

export type SubmissionStep =
  "upload" | "preview" | "ai-report" | "sign" | "confirmed";
