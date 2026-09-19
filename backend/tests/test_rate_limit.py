"""Tests for the in-process rate limiter on the upload and verify endpoints.

Includes how a client is identified when the app sits behind a reverse proxy:
the proxy's own address would otherwise put every caller in one window, and the
``X-Forwarded-For`` header it adds is only trustworthy from a configured proxy.
"""

import pytest
from httpx import AsyncClient
from starlette.requests import Request

from app.config import settings
from app.core.rate_limit import _resolved_client_host
from tests.conftest import SAMPLE_HASH, unique_sample_csv


async def _upload(client: AsyncClient, forwarded_for: str | None = None):
    """POST a unique upload so repeated calls do not collide on dataset_hash."""
    headers = {"X-Forwarded-For": forwarded_for} if forwarded_for else None
    return await client.post(
        "/api/v1/datasets",
        files={"file": ("test.csv", unique_sample_csv(), "text/csv")},
        headers=headers,
    )


def _request(peer: str | None, forwarded_for: str | None = None) -> Request:
    """A minimal request whose peer and X-Forwarded-For the resolver can read."""
    headers = []
    if forwarded_for is not None:
        headers.append((b"x-forwarded-for", forwarded_for.encode()))
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": headers,
            "client": (peer, 1234) if peer else None,
            "query_string": b"",
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )


@pytest.mark.asyncio
async def test_upload_returns_429_after_the_limit_is_exceeded(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "rate_limit_requests", 2)

    first = await _upload(client)
    second = await _upload(client)
    third = await _upload(client)

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert third.status_code == 429
    assert third.headers["Retry-After"] == str(settings.rate_limit_window_seconds)
    assert "Rate limit exceeded" in third.json()["detail"]


@pytest.mark.asyncio
async def test_verify_returns_429_after_the_limit_is_exceeded(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    mock_verify_on_chain_not_found,
) -> None:
    monkeypatch.setattr(settings, "rate_limit_requests", 1)

    first = await client.post("/api/v1/verify", params={"dataset_hash": SAMPLE_HASH})
    second = await client.post("/api/v1/verify", params={"dataset_hash": SAMPLE_HASH})

    assert first.status_code == 200, first.text
    assert second.status_code == 429


@pytest.mark.asyncio
async def test_limit_is_tracked_per_endpoint(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    mock_verify_on_chain_not_found,
) -> None:
    """An upload does not consume the verification endpoint's allowance."""
    monkeypatch.setattr(settings, "rate_limit_requests", 1)

    upload = await _upload(client)
    verify = await client.post("/api/v1/verify", params={"dataset_hash": SAMPLE_HASH})

    assert upload.status_code == 201, upload.text
    assert verify.status_code == 200, verify.text


@pytest.mark.asyncio
async def test_rate_limiting_can_be_disabled(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    monkeypatch.setattr(settings, "rate_limit_requests", 1)

    for _ in range(3):
        response = await _upload(client)
        assert response.status_code == 201, response.text


# ── Clients behind a reverse proxy ────────────────────────────────


def test_forwarded_header_is_ignored_without_trusted_proxies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trusting the header by default would let any caller choose its bucket."""
    monkeypatch.setattr(settings, "trusted_proxies", [])

    assert _resolved_client_host(_request("127.0.0.1", "1.2.3.4")) == "127.0.0.1"


def test_forwarded_header_is_ignored_from_an_untrusted_peer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only a configured proxy's header is trusted; anyone else is the client."""
    monkeypatch.setattr(settings, "trusted_proxies", ["10.0.0.1"])

    assert _resolved_client_host(_request("127.0.0.1", "1.2.3.4")) == "127.0.0.1"


def test_client_is_taken_from_a_trusted_proxies_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "trusted_proxies", ["127.0.0.1"])

    assert _resolved_client_host(_request("127.0.0.1", "1.2.3.4")) == "1.2.3.4"


def test_trusted_hops_are_skipped_to_find_the_real_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A client behind two known proxies is not identified as the inner proxy."""
    monkeypatch.setattr(settings, "trusted_proxies", ["127.0.0.1", "10.0.0.5"])

    assert _resolved_client_host(_request("127.0.0.1", "1.2.3.4, 10.0.0.5")) == "1.2.3.4"


def test_all_proxy_chain_falls_back_to_the_leftmost_hop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "trusted_proxies", ["127.0.0.1", "10.0.0.5"])

    assert _resolved_client_host(_request("127.0.0.1", "10.0.0.5")) == "10.0.0.5"


def test_trusted_peer_without_a_header_is_its_own_bucket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A trusted proxy that forwards no header is still counted, not dropped."""
    monkeypatch.setattr(settings, "trusted_proxies", ["127.0.0.1"])

    assert _resolved_client_host(_request("127.0.0.1")) == "127.0.0.1"


def test_trusted_proxy_matching_accepts_a_cidr(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cloud load balancers are ranges, not single addresses."""
    monkeypatch.setattr(settings, "trusted_proxies", ["10.0.0.0/8"])

    assert _resolved_client_host(_request("10.1.2.3", "1.2.3.4")) == "1.2.3.4"


def test_addresses_are_normalised_so_one_host_is_one_bucket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "trusted_proxies", ["127.0.0.1"])

    assert _resolved_client_host(_request("127.0.0.1", "0:0:0:0:0:0:0:1")) == "::1"


def test_blank_header_entries_are_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "trusted_proxies", ["127.0.0.1"])

    assert _resolved_client_host(_request("127.0.0.1", " 1.2.3.4 , , ")) == "1.2.3.4"


def test_blank_and_malformed_proxy_entries_are_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bad entry must not disable the good ones (boot rejects it separately)."""
    monkeypatch.setattr(settings, "trusted_proxies", ["", "not-a-cidr", "127.0.0.1"])

    assert _resolved_client_host(_request("127.0.0.1", "1.2.3.4")) == "1.2.3.4"


def test_non_ip_header_entry_is_returned_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A junk entry is its own bucket rather than a crash."""
    monkeypatch.setattr(settings, "trusted_proxies", ["127.0.0.1"])

    assert _resolved_client_host(_request("127.0.0.1", "not-an-ip")) == "not-an-ip"


def test_all_blank_header_entries_fall_back_to_the_peer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "trusted_proxies", ["127.0.0.1"])

    assert _resolved_client_host(_request("127.0.0.1", ", ,")) == "127.0.0.1"


@pytest.mark.asyncio
async def test_trusted_proxy_gives_each_forwarded_client_its_own_window(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The point of the setting: distinct clients no longer share one bucket."""
    monkeypatch.setattr(settings, "rate_limit_requests", 1)
    monkeypatch.setattr(settings, "trusted_proxies", ["127.0.0.1"])

    first = await _upload(client, forwarded_for="1.1.1.1")
    second = await _upload(client, forwarded_for="2.2.2.2")
    again = await _upload(client, forwarded_for="1.1.1.1")

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text  # different client, own allowance
    assert again.status_code == 429  # same client, allowance spent


@pytest.mark.asyncio
async def test_untrusted_peer_still_shares_one_window(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A header from a peer that is not a configured proxy changes nothing."""
    monkeypatch.setattr(settings, "rate_limit_requests", 1)
    monkeypatch.setattr(settings, "trusted_proxies", ["10.0.0.1"])

    first = await _upload(client, forwarded_for="1.1.1.1")
    second = await _upload(client, forwarded_for="2.2.2.2")

    assert first.status_code == 201, first.text
    assert second.status_code == 429
