import logging
from ipaddress import ip_network

from pydantic_settings import BaseSettings, SettingsConfigDict

# The only value for which the permissive development defaults below are
# considered safe. Anything else is a deployment, and validate_boot_settings()
# refuses to start one that is missing what it needs.
DEVELOPMENT = "development"

logger = logging.getLogger(__name__)


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

    # ── Deployment environment ────────────────────────────────────
    # "development" keeps the permissive defaults (no contract required, and no
    # auth once the opt-in below is set). Any other value is a real deployment,
    # which ``validate_boot_settings`` gates on the settings a deployment cannot
    # do without. Set ``ENVIRONMENT=production`` in production.
    environment: str = DEVELOPMENT

    api_cors_origins: list[str] = ["http://localhost:5173"]
    # Methods and headers the frontend actually sends. Reads are GET; uploads,
    # anchoring, batch submission, and verification are POST. The browser
    # attaches Content-Type and, on writes, X-API-Key. A wildcard here would
    # also let any site's script attach arbitrary headers to allowed origins,
    # so the list is pinned to what the frontend uses.
    api_cors_methods: list[str] = ["GET", "POST"]
    api_cors_headers: list[str] = ["Content-Type", "X-API-Key"]

    # ── Authentication ────────────────────────────────────────────
    # Comma-separated keys accepted in the ``X-API-Key`` header on the write
    # endpoints (uploads and anchoring). Empty disables authentication, but only
    # with the explicit opt-in below: with no key and no opt-in the app refuses
    # to start, so an open write API can never happen by omission. Verification
    # and health stay public on purpose — permissionless verification is a
    # feature, not an oversight.
    api_keys: str = ""

    # Explicit opt-in to run with authentication disabled. Needed only when
    # ``api_keys`` is empty, and honoured in development only:
    # ``validate_boot_settings`` refuses to start without a key in any other
    # environment, so a deployment that never set ``ENVIRONMENT`` still fails
    # closed rather than serving an open write API. Choosing it logs a warning
    # at boot.
    allow_unauthenticated_writes: bool = False

    # ── Abuse limits ──────────────────────────────────────────────
    # The upload and verification endpoints parse and hash a file (and
    # verification also calls the Soroban RPC), so an unauthenticated caller
    # could otherwise repeat that work without limit. Requests are counted per
    # client IP over a sliding window.
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 30
    rate_limit_window_seconds: int = 60
    # Addresses (or CIDRs) of the reverse proxies in front of this app whose
    # ``X-Forwarded-For`` header may be trusted when identifying a client for
    # the rate limiter. Empty (the default) ignores the header entirely, which
    # is what a directly reached app needs: trusting it then would let any
    # caller mint a fresh bucket per request. Set it to the proxy that
    # terminates connections to this app — a local nginx on the same host, for
    # example, is ``127.0.0.1``.
    trusted_proxies: list[str] = []

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


def validate_boot_settings() -> None:
    """Refuse to start an unsafe deployment before it can serve a request.

    The development defaults are deliberately permissive so a fresh checkout
    runs with little setup: an empty contract, CORS pointing at the Vite dev
    server, and — with an explicit opt-in — no authentication. Those same
    defaults are unsafe in a deployment, and each one fails in a way that is
    worse the later it is discovered: an open write endpoint, a browser blocked
    at preflight, an anchor that cannot be built. This runs once at app creation
    and turns the whole set into one startup error.

    One setting is checked in *every* environment, development included: an
    empty ``API_KEYS``. It is the only default whose failure mode is a wide-open
    write API, so disabling authentication is an explicit choice
    (``ALLOW_UNAUTHENTICATED_WRITES=true``) rather than something a checkout —
    or a deployment that never set ``ENVIRONMENT`` — drifts into. Choosing it
    logs a warning instead of starting quietly. Outside development the opt-in
    is ignored: a deployment always needs a key.

    Development (``ENVIRONMENT=development``) is exempt from the rest by design.

    Raises:
        ValueError: If authentication is off without the opt-in, or a
            deployment-critical setting is missing or still at its development
            default.
    """
    problems: list[str] = []

    auth_disabled = not settings.api_keys.strip()
    if auth_disabled:
        if settings.environment != DEVELOPMENT:
            problems.append("API_KEYS is empty, so every write endpoint would be unauthenticated")
        elif not settings.allow_unauthenticated_writes:
            problems.append(
                "API_KEYS is empty, so every write endpoint would be unauthenticated. "
                "Set at least one key, or set ALLOW_UNAUTHENTICATED_WRITES=true to run "
                "without authentication in development"
            )

    # A mistyped proxy address would silently fall back to counting every caller
    # by the proxy's own IP, which is the failure this setting exists to fix, so
    # it is a boot error rather than something ignored at request time.
    for entry in settings.trusted_proxies:
        if not entry.strip():
            continue
        try:
            ip_network(entry.strip(), strict=False)
        except ValueError:
            problems.append(
                f"TRUSTED_PROXIES entry {entry!r} is not an IP address or CIDR, "
                "so it would be ignored and clients would be counted by proxy IP"
            )

    if settings.environment != DEVELOPMENT:
        if not settings.contract_id:
            problems.append("CONTRACT_ID is empty, so no anchor transaction can be built")
        if settings.api_cors_origins == ["http://localhost:5173"]:
            problems.append("API_CORS_ORIGINS is still the localhost development default")
        if settings.ttl_renewal_enabled and not settings.ttl_renewal_signer_secret:
            problems.append(
                "TTL_RENEWAL_ENABLED is on but TTL_RENEWAL_SIGNER_SECRET is unset, "
                "so renewals would fail at signing time"
            )

    if problems:
        raise ValueError(
            f"Refusing to start with ENVIRONMENT={settings.environment!r}: "
            + "; ".join(problems)
            + ". See docs/deployment.md for the production checklist."
        )

    if auth_disabled:
        logger.warning(
            "API_KEYS is empty and ALLOW_UNAUTHENTICATED_WRITES is on: every write "
            "endpoint is open to anyone who can reach this host. This is for local "
            "development only — set API_KEYS before deploying."
        )
