"""Tests for the deployment boot gate and the defaults it protects.

The development defaults are deliberately permissive so a fresh checkout runs
with no setup. These pin the other half of that bargain: a non-development
environment refuses to start without the settings a deployment cannot safely do
without, each of which would otherwise fail later and less clearly.
"""

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
    return monkeypatch


def test_development_defaults_still_start(monkeypatch: pytest.MonkeyPatch) -> None:
    """Development is exempt: the empty contract and no auth are its defaults."""
    monkeypatch.setattr(settings, "environment", DEVELOPMENT)
    monkeypatch.setattr(settings, "contract_id", "")
    monkeypatch.setattr(settings, "api_keys", "")

    validate_boot_settings()
    create_app()  # the gate lets a development app through


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


def test_cors_is_pinned_to_the_frontend_methods_and_headers() -> None:
    """The frontend only ever sends reads (GET) and writes (POST)."""
    assert settings.api_cors_methods == ["GET", "POST"]
    assert settings.api_cors_headers == ["Content-Type", "X-API-Key"]
