.PHONY: build test lint clean deploy-testnet invoke-anchor invoke-verify

# Same path as the repository's CI, release and deploy workflows.
#
# `stellar contract build` rather than `cargo build`, and not by preference:
# soroban-sdk 28's build script refuses to compile for any wasm target unless the
# build system sets SOROBAN_SDK_BUILD_SYSTEM_SUPPORTS_SPEC_SHAKING_V2, which only
# the CLI does. It will not emit a contract whose spec has not been shaken. So
# the target moved from wasm32-unknown-unknown (unsupported since Rust 1.82
# anyway) to wasm32v1-none, and the build command moved with it.
WASM := target/wasm32v1-none/release/geoguard_ledger.wasm

build:
	stellar contract build
	@echo "WASM built: $(WASM)"

test:
	cargo test --verbose

lint:
	cargo fmt --all -- --check
	cargo clippy -- -D warnings

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
