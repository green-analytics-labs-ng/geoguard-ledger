.PHONY: build test lint clean deploy

build:
	stellar contract build --optimize
	@echo "WASM built: target/wasm32v1-none/release/geoguard_ledger.wasm"

test:
	cargo test --verbose

lint:
	cargo fmt --all -- --check
	cargo clippy -- -D warnings

clean:
	cargo clean

deploy-testnet:
	stellar contract deploy \
		--wasm target/wasm32v1-none/release/geoguard_ledger.wasm \
		--source $$DEPLOYER_SECRET \
		--network testnet

invoke-anchor:
	stellar contract invoke \
		--id $$CONTRACT_ID \
		--source $$SUBMITTER_SECRET \
		--network testnet \
		-- anchor_hash \
		--submitter $$SUBMITTER_PK \
		--dataset_hash $$DATASET_HASH \
		--anomaly_score 420 \
		--model_version isoforest_v1

invoke-verify:
	stellar contract invoke \
		--id $$CONTRACT_ID \
		--source $$SUBMITTER_SECRET \
		--network testnet \
		-- verify_integrity \
		--dataset_hash $$DATASET_HASH
