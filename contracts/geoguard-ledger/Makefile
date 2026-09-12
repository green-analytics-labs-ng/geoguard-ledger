.PHONY: build test lint clean deploy-testnet invoke-anchor invoke-verify

# Same target and path as the repository's CI and deploy workflows. Building
# with `stellar contract build --optimize` instead writes to
# target/wasm32v1-none/release/, so change this if you switch.
WASM := target/wasm32-unknown-unknown/release/geoguard_ledger.wasm

build:
	cargo build --target wasm32-unknown-unknown --release
	@echo "WASM built: $(WASM)"

test:
	cargo test --verbose

lint:
	cargo fmt --all -- --check
	cargo clippy --target wasm32-unknown-unknown -- -D warnings

clean:
	cargo clean

# Deployment lives in the repository script so that local runs, CI, and the
# manual deploy workflow all execute the same code.
deploy-testnet: build
	../../scripts/deploy_contract.sh --network testnet

invoke-anchor:
	stellar contract invoke \
		--id $$CONTRACT_ID \
		--source-account $$SUBMITTER_SECRET \
		--network testnet \
		-- anchor_hash \
		--submitter $$SUBMITTER_PK \
		--dataset_hash $$DATASET_HASH \
		--anomaly_score 420 \
		--model_version isoforest_v1

invoke-verify:
	stellar contract invoke \
		--id $$CONTRACT_ID \
		--source-account $$SUBMITTER_SECRET \
		--network testnet \
		-- verify_integrity \
		--dataset_hash $$DATASET_HASH
