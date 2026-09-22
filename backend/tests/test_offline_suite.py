"""Tests that the suite itself never reaches the network.

These pin what ``offline_soroban_by_default`` in ``conftest.py`` guarantees.
Without them, deleting that fixture would break nothing here: the tests it
protects assert on application behaviour, not on being offline, so the suite
would quietly go back to dialling Testnet from a developer's machine — which is
exactly what it did before, without a single failure or warning.

Measured with a socket-level counter over the whole suite, the leak was 48
outbound connections under a local ``.env`` that sets ``CONTRACT_ID``, and zero
without one.
"""

import pytest
from httpx import AsyncClient

from app.config import settings
from app.services import soroban
from app.services.soroban import TESTNET_NETWORK_PASSPHRASE


def test_no_contract_is_configured() -> None:
    """A local ``.env`` must not decide what the suite runs against.

    CI has no ``.env`` and so no ``CONTRACT_ID``; a developer's does. Pinning it
    empty is what makes the two runs behave the same, and it is also what keeps
    the on-chain lookups on their "contract not deployed" path instead of
    reaching Testnet.
    """
    assert settings.contract_id == ""


def test_the_configured_network_is_the_testnet_default() -> None:
    """The passphrase picks the network, so a local ``.env`` must not move it."""
    assert settings.soroban_network_passphrase == TESTNET_NETWORK_PASSPHRASE


def test_the_rpc_client_refuses_to_open_a_connection() -> None:
    """Any unmocked call fails loudly here rather than silently going out.

    ``test_soroban.py`` and its neighbours fake ``SorobanServer`` deliberately.
    This is the backstop for a test that forgets to: with a real client these
    calls would attempt a connection, which is how the live traffic appeared in
    the first place.
    """
    server = soroban._get_server()

    with pytest.raises(ConnectionError, match="offline"):
        server.get_health()
    with pytest.raises(ConnectionError, match="offline"):
        server.load_account("G" + "A" * 55)


@pytest.mark.asyncio
async def test_health_endpoint_reports_unreachable_without_being_mocked(
    client: AsyncClient,
) -> None:
    """``GET /health`` probes the RPC for real, so offline it has to say so.

    This is the endpoint that reached the network on every run, including in
    CI, where the call happened to succeed and report "connected". Its own test
    only asserts the status code, so only this pins the offline behaviour.
    """
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["soroban_rpc"] == "unreachable"
