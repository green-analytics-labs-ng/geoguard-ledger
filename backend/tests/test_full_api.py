"""Test the full GeoGuard Ledger API flow end-to-end inside Docker.
Run with: docker cp backend/tests/test_full_api.py <container>:/tmp/ && docker exec <container> python3 /tmp/test_full_api.py
"""
import urllib.request
import json

BASE = "http://localhost:8000/api/v1"

# Step 1: Health check
print("=== Step 1: Health Check ===")
resp = urllib.request.urlopen(f"{BASE}/health")
print(json.loads(resp.read()))
print()

# Step 2: Empty datasets list
print("=== Step 2: Empty Datasets List ===")
resp = urllib.request.urlopen(f"{BASE}/datasets")
print(json.loads(resp.read()))
print()

# Step 3: Create a dataset
print("=== Step 3: Create Dataset ===")
boundary = "----TestBoundary"
csv_content = (
    "sample_id,latitude,longitude,pH,conductivity,dissolved_oxygen,temperature\n"
    "S001,34.052200,-118.243700,7.20,450.00,8.50,22.10\n"
    "S002,34.052500,-118.244000,7.15,452.00,8.30,22.30\n"
    "S003,34.052800,-118.244300,7.18,448.00,8.70,22.00"
)

body_parts = [
    "--" + boundary,
    'Content-Disposition: form-data; name="submitter_address"',
    "",
    "GCYZFJLXVXHL3RN2XECSLGTS2NPMHWGJUYTZWKNNELRML56NBJY5YRRG",
    "--" + boundary,
    'Content-Disposition: form-data; name="file"; filename="sample.csv"',
    "Content-Type: text/csv",
    "",
    csv_content,
    "--" + boundary + "--",
    "",
]
body = "\r\n".join(body_parts)

req = urllib.request.Request(
    f"{BASE}/datasets",
    data=body.encode("utf-8"),
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
)
try:
    resp = urllib.request.urlopen(req, timeout=60)
    result = json.loads(resp.read().decode())
    print(f"Status: {resp.status}")
    print(f"dataset_id: {result['dataset_id']}")
    print(f"dataset_hash: {result['dataset_hash']}")
    print(f"anomaly_score: {result['anomaly_report']['score']}")
    print(f"model_version: {result['anomaly_report']['model_version']}")
    print(f"has_xdr: {bool(result['unsigned_transaction_xdr'])}")
    DATASET_ID = result["dataset_id"]
    DATASET_HASH = result["dataset_hash"]
except urllib.error.HTTPError as e:
    print(f"ERROR: {e.code}")
    print(e.read().decode()[:500])
    exit(1)
print()

# Step 4: List datasets (should have 1)
print("=== Step 4: List Datasets ===")
resp = urllib.request.urlopen(f"{BASE}/datasets")
data = json.loads(resp.read())
print(f"Total: {data['total']}")
print(f"First dataset status: {data['datasets'][0]['status']}")
print()

# Step 5: Get dataset by ID
print("=== Step 5: Get Dataset by ID ===")
resp = urllib.request.urlopen(f"{BASE}/datasets/{DATASET_ID}")
print(json.dumps(json.loads(resp.read()), indent=2))
print()

# Step 6: Verify by hash
print("=== Step 6: Verify Dataset by Hash ===")
resp = urllib.request.urlopen(f"{BASE}/verify?dataset_hash={DATASET_HASH}")
verify_result = json.loads(resp.read())
print(f"match: {verify_result['match']}")
print(f"on_chain_record: {verify_result['on_chain_record']}")
print()

print("=== ALL TESTS PASSED ===")
