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

    # Maximum accepted upload size in bytes. The frontend enforces the same
    # limit client-side, but that check is trivially bypassed by calling the
    # API directly, so it is enforced again here before the body is buffered.
    max_upload_size_bytes: int = 50 * 1024 * 1024  # 50 MB

    # Maximum number of datasets in a single Merkle batch. Bounds the work a
    # single request does (tree build, proof generation, and transaction
    # simulation) and keeps the simulated resource footprint within RPC limits.
    max_batch_size: int = 1024

    ai_model_version: str = "isoforest_v1"
    ai_anomaly_threshold: float = 0.20
    # Toggle the domain-informed geochemical plausibility checks that run
    # alongside the statistical anomaly model.
    geochemical_validation_enabled: bool = True

    log_level: str = "INFO"


settings = Settings()
