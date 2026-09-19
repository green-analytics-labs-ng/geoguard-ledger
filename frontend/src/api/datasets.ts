import client, { UPLOAD_TIMEOUT_MS } from "./client";
import type { DatasetAnchorResponse, DatasetCreateResponse, DatasetResponse } from "../types";

/**
 * Upload a file to be canonicalized, hashed, and scored.
 *
 * No wallet is involved: nothing is committed to the network here, so there is
 * no transaction to sign yet. Call `anchorDataset` when the researcher is ready
 * to sign.
 */
export async function uploadCsv(file: File): Promise<DatasetCreateResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await client.post("/datasets", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    // Analyzing an upload is the slowest thing this API does, so it gets the
    // longer deadline rather than the client's default.
    timeout: UPLOAD_TIMEOUT_MS,
  });
  return data;
}

/**
 * Bind a submitter address to an analyzed dataset and get the transaction to sign.
 *
 * This is the wallet step: the address becomes the transaction's source account
 * and the dataset's recorded submitter.
 */
export async function anchorDataset(
  datasetId: string,
  submitterAddress: string,
): Promise<DatasetAnchorResponse> {
  const { data } = await client.post(`/datasets/${datasetId}/anchor`, {
    submitter_address: submitterAddress,
  });
  return data;
}

export async function submitDataset(datasetId: string, signedTransactionXdr: string) {
  const { data } = await client.post(`/datasets/${datasetId}/submit`, {
    signed_transaction_xdr: signedTransactionXdr,
  });
  return data;
}

export async function listDatasets(): Promise<{
  datasets: DatasetResponse[];
  total: number;
}> {
  const { data } = await client.get("/datasets");
  return data;
}

export async function getDataset(datasetId: string): Promise<DatasetResponse> {
  const { data } = await client.get(`/datasets/${datasetId}`);
  return data;
}
