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
  created_at: string;
  anchored_at?: string;
}

export interface VerifyResult {
  match: boolean;
  on_chain_record: AnchorRecord | null;
  local_record: DatasetResponse | null;
  re_computed_hash?: string;
}

export interface CsvPreview {
  headers: string[];
  rows: string[][];
  totalRows: number;
}

export type SubmissionStep = "upload" | "preview" | "ai-report" | "sign" | "confirmed";
