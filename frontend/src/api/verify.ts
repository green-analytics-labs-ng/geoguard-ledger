import client, { UPLOAD_TIMEOUT_MS } from "./client";
import type { VerifyResult } from "../types";

/**
 * Verification calls take an optional `AbortSignal` so a caller that unmounts
 * (or runs a second search) can drop the request it no longer wants. Without
 * one, a slow answer arrives after the page is gone and React is asked to
 * update a component that no longer exists.
 */

export async function verifyByHash(
  datasetHash: string,
  signal?: AbortSignal,
): Promise<VerifyResult> {
  const { data } = await client.post("/verify", null, {
    params: { dataset_hash: datasetHash },
    signal,
  });
  return data;
}

export async function verifyByFile(file: File, signal?: AbortSignal): Promise<VerifyResult> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await client.post("/verify", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    // The server re-canonicalizes the file and re-computes its hash, which is
    // the same work an upload does.
    timeout: UPLOAD_TIMEOUT_MS,
    signal,
  });
  return data;
}

export async function verifyById(datasetId: string, signal?: AbortSignal): Promise<VerifyResult> {
  const { data } = await client.post("/verify", null, {
    params: { dataset_id: datasetId },
    signal,
  });
  return data;
}
