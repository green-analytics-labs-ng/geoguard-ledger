"""Tests for the deployment boot gate and the defaults it protects.

The development defaults are deliberately permissive so a fresh checkout runs
with little setup. These pin the other half of that bargain: authentication is
gated in *every* environment — an empty ``API_KEYS`` needs an explicit
``ALLOW_UNAUTHENTICATED_WRITES`` opt-in, and that opt-in is development only —
and a non-development environment additionally refuses to start without the
other settings a deployment cannot safely do without.
"""

import logging

import pytest

from app.config import DEVELOPMENT, settings, validate_boot_settings
from app.main import create_app


@pytest.fixture
def production(
    monkeypatch: pytest.MonkeyPatch, disable_auth_by_default: None
) -> pytest.MonkeyPatch:
    """A valid production configuration, returned so a test can break one field.

    Depends on ``disable_auth_by_default`` explicitly so this fixture applies
    after the autouse one that clears ``API_KEYS`` for every test.
    """
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "contract_id", "C" + "A" * 55)
    monkeypatch.setattr(settings, "api_keys", "a-deployment-key")
    monkeypatch.setattr(settings, "api_cors_origins", ["https://app.example.com"])
    monkeypatch.setattr(settings, "ttl_renewal_enabled", False)
    monkeypatch.setattr(settings, "ttl_renewal_signer_secret", "")
    # A deployment never opts out of auth, so the empty-API_KEYS check applies.
    monkeypatch.setattr(settings, "allow_unauthenticated_writes", False)
    return monkeypatch


def test_development_requires_an_explicit_auth_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Development is exempt from the deployment checks, but not from choosing
    whether writes are authenticated: an empty API_KEYS fails closed."""
    monkeypatch.setattr(settings, "environment", DEVELOPMENT)
    monkeypatch.setattr(settings, "contract_id", "")
    monkeypatch.setattr(settings, "api_keys", "")
    monkeypatch.setattr(settings, "allow_unauthenticated_writes", False)

    with pytest.raises(ValueError, match="API_KEYS"):
        validate_boot_settings()


def test_development_starts_once_the_opt_in_is_explicit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The opt-in is what lets a checkout run without authentication."""
    monkeypatch.setattr(settings, "environment", DEVELOPMENT)
    monkeypatch.setattr(settings, "contract_id", "")
    monkeypatch.setattr(settings, "api_keys", "")
    monkeypatch.setattr(settings, "allow_unauthenticated_writes", True)

    validate_boot_settings()
    create_app()


def test_configured_keys_need_no_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    """The opt-in only concerns running *without* auth, so a key alone suffices."""
    monkeypatch.setattr(settings, "environment", DEVELOPMENT)
    monkeypatch.setattr(settings, "contract_id", "")
    monkeypatch.setattr(settings, "api_keys", "a-key")
    monkeypatch.setattr(settings, "allow_unauthenticated_writes", False)

    validate_boot_settings()
    create_app()


def test_running_without_auth_warns_loudly(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Disabling auth is allowed, but never quiet."""
    monkeypatch.setattr(settings, "environment", DEVELOPMENT)
    monkeypatch.setattr(settings, "api_keys", "")
    monkeypatch.setattr(settings, "allow_unauthenticated_writes", True)

    with caplog.at_level(logging.WARNING, logger="app.config"):
        validate_boot_settings()

    assert any(
        "API_KEYS is empty" in record.getMessage() and "open" in record.getMessage()
        for record in caplog.records
    )


def test_valid_production_settings_start(production: pytest.MonkeyPatch) -> None:
    validate_boot_settings()
    create_app()


def test_production_requires_a_contract_id(production: pytest.MonkeyPatch) -> None:
    production.setattr(settings, "contract_id", "")

    with pytest.raises(ValueError, match="CONTRACT_ID"):
        validate_boot_settings()


def test_production_requires_authentication(production: pytest.MonkeyPatch) -> None:
    """An empty key list means every write endpoint would be open."""
    production.setattr(settings, "api_keys", "")

    with pytest.raises(ValueError, match="API_KEYS"):
        validate_boot_settings()


def test_production_cannot_opt_out_of_authentication(
    production: pytest.MonkeyPatch,
) -> None:
    """The opt-in is a development convenience, not a way to ship an open API."""
    production.setattr(settings, "api_keys", "")
    production.setattr(settings, "allow_unauthenticated_writes", True)

    with pytest.raises(ValueError, match="API_KEYS"):
        validate_boot_settings()


def test_production_rejects_the_localhost_cors_default(production: pytest.MonkeyPatch) -> None:
    production.setattr(settings, "api_cors_origins", ["http://localhost:5173"])

    with pytest.raises(ValueError, match="API_CORS_ORIGINS"):
        validate_boot_settings()


def test_renewal_without_a_signer_is_rejected(production: pytest.MonkeyPatch) -> None:
    """Spending fees needs a key, so enabled-without-a-signer is a boot error."""
    production.setattr(settings, "ttl_renewal_enabled", True)

    with pytest.raises(ValueError, match="TTL_RENEWAL_SIGNER_SECRET"):
        validate_boot_settings()


def test_renewal_with_a_signer_is_allowed(production: pytest.MonkeyPatch) -> None:
    production.setattr(settings, "ttl_renewal_enabled", True)
    production.setattr(settings, "ttl_renewal_signer_secret", "S" + "A" * 55)

    validate_boot_settings()


def test_every_problem_is_reported_at_once(production: pytest.MonkeyPatch) -> None:
    """One start should surface all of them, not make the operator replay them."""
    production.setattr(settings, "contract_id", "")
    production.setattr(settings, "api_keys", "")

    with pytest.raises(ValueError) as caught:
        validate_boot_settings()

    message = str(caught.value)
    assert "CONTRACT_ID" in message
    assert "API_KEYS" in message


def test_boot_gate_is_wired_into_app_creation(production: pytest.MonkeyPatch) -> None:
    """The check belongs to boot, so creating the app is what rejects it."""
    production.setattr(settings, "api_keys", "")

    with pytest.raises(ValueError, match="API_KEYS"):
        create_app()


def test_malformed_trusted_proxy_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """A typo would silently restore the "every caller is the proxy" bug."""
    monkeypatch.setattr(settings, "environment", DEVELOPMENT)
    monkeypatch.setattr(settings, "contract_id", "")
    monkeypatch.setattr(settings, "api_keys", "")
    monkeypatch.setattr(settings, "allow_unauthenticated_writes", True)
    monkeypatch.setattr(settings, "trusted_proxies", ["127.0.0.1", "", "not-an-address"])

    with pytest.raises(ValueError, match="TRUSTED_PROXIES"):
        validate_boot_settings()


def test_cors_is_pinned_to_the_frontend_methods_and_headers() -> None:
    """The frontend only ever sends reads (GET) and writes (POST)."""
    assert settings.api_cors_methods == ["GET", "POST"]
    assert settings.api_cors_headers == ["Content-Type", "X-API-Key"]
