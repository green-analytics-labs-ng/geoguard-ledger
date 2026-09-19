from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://geoguard:geoguard_dev@localhost:5432/geoguard_ledger"
    soroban_rpc_url: str = "https://soroban-testnet.stellar.org"
    soroban_network_passphrase: str = "Test SDF Network ; September 2015"
    contract_id: str = ""
    # Timeout (seconds) for the Soroban RPC probe used by GET /health.
    soroban_rpc_health_timeout_seconds: float = 3.0

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_cors_origins: list[str] = ["http://localhost:5173"]

    # ── Authentication ────────────────────────────────────────────
    # Comma-separated keys accepted in the ``X-API-Key`` header on the write
    # endpoints (uploads and anchoring). Empty disables authentication, which
    # is the development default so a local checkout runs without setup;
    # deployments are expected to set at least one key. Verification and health
    # stay public on purpose — permissionless verification is a feature, not an
    # oversight.
    api_keys: str = ""

    # ── Abuse limits ──────────────────────────────────────────────
    # The upload and verification endpoints parse and hash a file (and
    # verification also calls the Soroban RPC), so an unauthenticated caller
    # could otherwise repeat that work without limit. Requests are counted per
    # client IP over a sliding window.
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 30
    rate_limit_window_seconds: int = 60

    # Maximum accepted upload size in bytes. The frontend enforces the same
    # limit client-side, but that check is trivially bypassed by calling the
    # API directly, so it is enforced again here before the body is buffered.
    max_upload_size_bytes: int = 50 * 1024 * 1024  # 50 MB

    # Maximum number of datasets in a single Merkle batch. Bounds the work a
    # single request does (tree build, proof generation, and transaction
    # simulation) and keeps the simulated resource footprint within RPC limits.
    max_batch_size: int = 1024

    # ── TTL renewal ───────────────────────────────────────────────
    # On-chain anchors are Persistent ledger entries, so they expire unless
    # something extends them. Two kinds need renewing: a batch's Merkle root
    # (`extend_root_ttl`) and a dataset's own record when it was anchored
    # individually (`extend_ttl`). The write-time bumps in
    # contracts/geoguard-ledger/src/storage.rs keep both alive for ~180 days; a
    # scheduled job renews them before that runs out, so verification keeps
    # answering without anyone restoring archived entries.
    #
    # Master switch for the renewal job. Off by default: renewal spends real
    # fees from the operational account, so it must be opted into.
    ttl_renewal_enabled: bool = False
    # StrKey-encoded secret key (S...) of the operational account that pays
    # renewal fees. Without it the job refuses to run — the backend never holds
    # a researcher's key, only this dedicated "rent payer".
    ttl_renewal_signer_secret: str = ""
    # Ledgers a renewal extends an entry to (~180 days at 5s/ledger). Mirrors
    # the contract's ROOT_TTL_EXTEND_TO and RECORD_TTL_EXTEND_TO, which are the
    # same budget; change all three together.
    ttl_renewal_extend_to_ledgers: int = 3_110_400
    # Renew once an entry has less than this much life left. Must stay below the
    # contract's renewal margin (~174 days) so the call is not a silent no-op.
    ttl_renewal_window_days: int = 30
    # Most entries a single job run will renew across both kinds, bounding fee
    # spend per run.
    ttl_renewal_max_entries_per_run: int = 20

    ai_model_version: str = "isoforest_v1"
    ai_anomaly_threshold: float = 0.20
    # Toggle the domain-informed geochemical plausibility checks that run
    # alongside the statistical anomaly model.
    geochemical_validation_enabled: bool = True

    log_level: str = "INFO"


settings = Settings()
