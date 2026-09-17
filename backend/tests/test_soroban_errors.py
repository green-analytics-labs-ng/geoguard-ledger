"""Unit tests for the errors the Soroban service raises to the API layer."""

import pytest

from app.config import settings
from app.core.exceptions import SubmitterAccountNotFoundError
from app.services.soroban import (
    FRIENDBOT_URL,
    TESTNET_NETWORK_PASSPHRASE,
    _unfunded_submitter_error,
)

ADDRESS = "GABCDEF123456789012345678901234567890123"
MAINNET_NETWORK_PASSPHRASE = "Public Global Stellar Network ; September 2015"


def test_unfunded_submitter_on_testnet_points_at_the_faucet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Testnet has a faucet, so the error names it along with the address."""
    monkeypatch.setattr(settings, "soroban_network_passphrase", TESTNET_NETWORK_PASSPHRASE)

    error = _unfunded_submitter_error(ADDRESS)

    assert isinstance(error, SubmitterAccountNotFoundError)
    assert error.status_code == 400
    assert ADDRESS in error.message
    assert f"{FRIENDBOT_URL}?addr={ADDRESS}" in error.message


def test_unfunded_submitter_on_mainnet_offers_no_faucet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mainnet has no faucet, so offering one would send the user nowhere."""
    monkeypatch.setattr(settings, "soroban_network_passphrase", MAINNET_NETWORK_PASSPHRASE)

    error = _unfunded_submitter_error(ADDRESS)

    assert error.status_code == 400
    assert FRIENDBOT_URL not in error.message
    assert "Mainnet" in error.message
