"""
End-to-end submission flow test.

This script simulates the full user journey:
1. Create a dataset (upload CSV, get hash + anomaly report + unsigned XDR)
2. Sign the XDR using the deployer secret (simulating Freighter wallet)
3. Submit the signed transaction to Stellar
4. Verify the on-chain proof

Run inside the Docker container:
  docker cp backend/tests/test_submission_flow.py <container>:/tmp/
  docker exec <container> uv run python3 /tmp/test_submission_flow.py
"""

import json
import urllib.request
import uuid

from stellar_sdk import Keypair, TransactionEnvelope

BASE = "http://localhost:8000/api/v1"

# Deployer keypair for signing (funded on Testnet, admin of the contract)
DEPLOYER_SECRET = "SDIYZRYM4XYA5IK37KFPI6HJZT2ONNMBRVLTAACQH6YXWD7X2TYGZXXV"
DEPLOYER_PK = "GCYZFJLXVXHL3RN2XECSLGTS2NPMHWGJUYTZWKNNELRML56NBJY5YRRG"


def api_post(path, body=None, headers=None, files=False):
    """Make a POST request to the API."""
    url = f"{BASE}{path}"
    if files:
        # Multipart form data for file uploads
        pass  # Handled separately
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url,
        data=data or None,
        headers=headers or {"Content-Type": "application/json"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def main():
    # ── Step 0: Health Check ──────────────────────────────────────
    print("=" * 60)
    print("STEP 0: Health Check")
    print("=" * 60)
    resp = urllib.request.urlopen(f"{BASE}/health")
    print(json.loads(resp.read()))
    print()

    # ── Step 1: Create Dataset ────────────────────────────────────
    print("=" * 60)
    print("STEP 1: Create Dataset")
    print("=" * 60)

    # Use a unique CSV to avoid hash collision with previous test data
    unique_id = uuid.uuid4().hex[:8]
    csv_content = (
        "sample_id,latitude,longitude,pH,conductivity,dissolved_oxygen,temperature\n"
        f"S001,34.052200,-118.243700,7.20,450.00,8.50,22.10\n"
        f"S002,34.052500,-118.244000,7.15,452.00,8.30,22.30\n"
        f"S003,34.052800,-118.244300,7.18,448.00,8.70,22.00\n"
        f"S004,34.053100,-118.244600,7.22,455.00,8.40,22.20\n"
        f"S005,34.053400,-118.244900,7.19,449.00,8.60,22.40\n"
        f"S006,{unique_id[:4]}.{unique_id[4:]},-118.250000,7.25,460.00,8.45,22.15"
    )

    boundary = "----WebKitFormBoundary" + unique_id
    body_parts = [
        f"--{boundary}",
        'Content-Disposition: form-data; name="submitter_address"',
        "",
        DEPLOYER_PK,
        f"--{boundary}",
        'Content-Disposition: form-data; name="file"; filename="sample.csv"',
        "Content-Type: text/csv",
        "",
        csv_content,
        f"--{boundary}--",
        "",
    ]
    body = "\r\n".join(body_parts)

    req = urllib.request.Request(
        f"{BASE}/datasets",
        data=body.encode("utf-8"),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    resp = urllib.request.urlopen(req, timeout=60)
    create_result = json.loads(resp.read().decode())
    dataset_id = create_result["dataset_id"]
    dataset_hash = create_result["dataset_hash"]
    unsigned_xdr = create_result["unsigned_transaction_xdr"]
    anomaly_score = create_result["anomaly_report"]["score"]
    model_version = create_result["anomaly_report"]["model_version"]

    print(f"Status: {resp.status}")
    print(f"dataset_id: {dataset_id}")
    print(f"dataset_hash: {dataset_hash}")
    print(f"anomaly_score: {anomaly_score}")
    print(f"model_version: {model_version}")
    print(f"has_xdr: {bool(unsigned_xdr)}")
    print(f"xdr_preview: {unsigned_xdr[:60]}...")
    print()

    # ── Step 2: Sign Transaction (simulating Freighter) ───────────
    print("=" * 60)
    print("STEP 2: Sign Transaction")
    print("=" * 60)

    kp = Keypair.from_secret(DEPLOYER_SECRET)
    network_passphrase = "Test SDF Network ; September 2015"

    envelope = TransactionEnvelope.from_xdr(unsigned_xdr, network_passphrase)
    envelope.sign(kp)
    signed_xdr = envelope.to_xdr()

    print(f"Signed XDR length: {len(signed_xdr)}")
    print(f"signed_xdr_preview: {signed_xdr[:60]}...")
    print()

    # ── Step 3: Submit Transaction ────────────────────────────────
    print("=" * 60)
    print("STEP 3: Submit Transaction")
    print("=" * 60)

    submit_body = json.dumps({"signed_transaction_xdr": signed_xdr}).encode()
    req = urllib.request.Request(
        f"{BASE}/datasets/{dataset_id}/submit",
        data=submit_body,
        headers={"Content-Type": "application/json"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        submit_result = json.loads(resp.read().decode())
        print(f"Status: {resp.status}")
        print(f"Status: {submit_result['status']}")
        print(f"Stellar Tx Hash: {submit_result['stellar_tx_hash']}")
        print(f"Ledger: {submit_result['ledger_number']}")
        print(f"Explorer URL: {submit_result['explorer_url']}")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()[:500]
        print(f"ERROR {e.code}: {error_body}")
        # Check if the issue is that the submitter isn't funded or other on-chain issue
        if e.code == 502:
            print("Transaction submission to Soroban RPC failed.")
            print("This may mean the simulation was rejected by the RPC.")
            print("Let's still verify the dataset status in the DB.")
        exit(1)
    print()

    # ── Step 4: Verify On-Chain ──────────────────────────────────
    print("=" * 60)
    print("STEP 4: Verify On-Chain")
    print("=" * 60)

    req = urllib.request.Request(f"{BASE}/verify?dataset_hash={dataset_hash}")
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        verify_result = json.loads(resp.read().decode())
        print(f"Status: {resp.status}")
        print(f"match: {verify_result['match']}")
        if verify_result["on_chain_record"]:
            ocr = verify_result["on_chain_record"]
            print("on_chain_record:")
            print(f"  dataset_hash: {ocr['dataset_hash']}")
            print(f"  anomaly_score: {ocr['anomaly_score']}")
            print(f"  model_version: {ocr['model_version']}")
            print(f"  submitter: {ocr['submitter']}")
            print(f"  timestamp: {ocr['timestamp']}")
    except urllib.error.HTTPError as e:
        print(f"Verify error {e.code}: {e.read().decode()[:300]}")
    print()

    # ── Step 5: Get Dataset Details ──────────────────────────────
    print("=" * 60)
    print("STEP 5: Dataset Details")
    print("=" * 60)

    req = urllib.request.Request(f"{BASE}/datasets/{dataset_id}")
    resp = urllib.request.urlopen(req, timeout=30)
    ds = json.loads(resp.read().decode())
    print(f"Status: {ds['status']}")
    print(f"Anchored at: {ds.get('anchored_at', 'N/A')}")
    print(f"Tx: {ds.get('stellar_tx_hash', 'N/A')}")
    print(f"Explorer: {ds.get('explorer_url', 'N/A')}")
    print()

    print("=" * 60)
    print("FLOW COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
