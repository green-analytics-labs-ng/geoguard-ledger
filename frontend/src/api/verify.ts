import client from "./client";
import type { VerifyResult } from "../types";

export async function verifyByHash(datasetHash: string): Promise<VerifyResult> {
  const { data } = await client.post("/verify", null, {
    params: { dataset_hash: datasetHash },
  });
  return data;
}

export async function verifyByFile(file: File): Promise<VerifyResult> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await client.post("/verify", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function verifyById(datasetId: string): Promise<VerifyResult> {
  const { data } = await client.post("/verify", null, {
    params: { dataset_id: datasetId },
  });
  return data;
}
