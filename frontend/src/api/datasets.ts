import client from "./client";
import type { DatasetCreateResponse, DatasetResponse } from "../types";

export async function uploadCsv(
  file: File,
  submitterAddress: string,
  hashColumns?: string[],
): Promise<DatasetCreateResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("submitter_address", submitterAddress);
  if (hashColumns) {
    hashColumns.forEach((col) => formData.append("hash_columns", col));
  }
  const { data } = await client.post("/datasets", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function submitDataset(
  datasetId: string,
  signedTransactionXdr: string,
) {
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
