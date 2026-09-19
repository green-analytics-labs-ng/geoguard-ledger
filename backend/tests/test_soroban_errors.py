"""Unit tests for the errors the Soroban service raises to the API layer."""

import pytest

from app.config import settings
from app.core.exceptions import AnchorAlreadyExistsError, SubmitterAccountNotFoundError
from app.services.soroban import (
    FRIENDBOT_URL,
    TESTNET_NETWORK_PASSPHRASE,
    _already_anchored_error,
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


def test_hash_already_anchored_maps_to_a_conflict() -> None:
    """Contract code 3 is a hash the ledger already holds — a conflict, not a retry."""
    error = _already_anchored_error("HostError: Error(Contract, #3)")

    assert isinstance(error, AnchorAlreadyExistsError)
    assert error.status_code == 409
    assert "hash" in error.message


def test_root_already_anchored_maps_to_a_conflict() -> None:
    """Contract code 6 is an anchored Merkle root, so the batch needs no second anchor."""
    error = _already_anchored_error("Error(Contract, #6)")

    assert isinstance(error, AnchorAlreadyExistsError)
    assert error.status_code == 409
    assert "Merkle root" in error.message


def test_unrelated_contract_error_code_is_not_a_conflict() -> None:
    """Any other contract error is a genuine failure and must not be called a duplicate."""
    assert _already_anchored_error("Error(Contract, #7)") is None


def test_non_contract_simulation_error_is_not_a_conflict() -> None:
    """A failure that never names the contract is never mislabelled as already anchored."""
    assert _already_anchored_error("Transaction simulation failed: timeout") is None


@pytest.mark.parametrize("simulation_error", ["Error(Contract, #3)", "Error( Contract , 3 )"])
def test_conflict_detection_tolerates_error_formatting(simulation_error: str) -> None:
    """RPC versions differ in spacing and the '#' prefix, so both forms must parse."""
    assert isinstance(_already_anchored_error(simulation_error), AnchorAlreadyExistsError)
