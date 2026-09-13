import client from "./client";
import type { BatchCreateResponse, BatchResponse, BatchSubmitResponse } from "../types";

/**
 * Build a Merkle root over the given datasets and get an unsigned anchoring
 * transaction. `datasetIds` order defines each dataset's leaf index.
 */
export async function createBatch(
  submitterAddress: string,
  datasetIds: string[],
): Promise<BatchCreateResponse> {
  const { data } = await client.post("/batches", {
    submitter_address: submitterAddress,
    dataset_ids: datasetIds,
  });
  return data;
}

export async function submitBatch(
  batchId: string,
  signedTransactionXdr: string,
): Promise<BatchSubmitResponse> {
  const { data } = await client.post(`/batches/${batchId}/submit`, {
    signed_transaction_xdr: signedTransactionXdr,
  });
  return data;
}

export async function listBatches(): Promise<{
  batches: BatchResponse[];
  total: number;
}> {
  const { data } = await client.get("/batches");
  return data;
}

export async function getBatch(batchId: string): Promise<BatchResponse> {
  const { data } = await client.get(`/batches/${batchId}`);
  return data;
}
