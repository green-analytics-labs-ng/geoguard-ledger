"""A small in-process rate limiter for the endpoints that do real work.

Both the dataset upload and the verification file mode parse and hash a file,
and verification also queries the Soroban RPC — work a caller could otherwise
repeat without limit. This bounds it per client IP over a sliding window.

Behind a reverse proxy the peer address is the proxy, so every caller would share
one window. Setting ``TRUSTED_PROXIES`` lets the limiter read the real client
from ``X-Forwarded-For`` — but only when the immediate peer is one of the
configured proxies, and only for the hops a proxy appended. A header from an
untrusted peer is ignored, so a caller cannot pick its own bucket.

The counters live in the process, so this guards against one abusive client
rather than acting as a distributed quota: behind several workers each process
tracks its own window, and a restart clears them. That is an acceptable Phase 1
trade-off; a shared store (e.g. Redis) can replace the storage without changing
the call sites.
"""

from collections.abc import Awaitable, Callable
from ipaddress import IPv4Network, IPv6Network, ip_address, ip_network
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request, status

from app.config import settings

_lock = Lock()
_hits: dict[str, list[float]] = {}


def reset_rate_limits() -> None:
    """Forget every recorded hit (used by tests to isolate windows)."""
    with _lock:
        _hits.clear()


def _normalise(address: str) -> str:
    """Canonical form of an IP address, so one host is always one bucket.

    ``::1`` and ``0:0:0:0:0:0:0:1`` name the same host; without this they would
    count separately. Anything that is not a bare address (a malformed header
    entry) is returned unchanged.
    """
    try:
        return str(ip_address(address))
    except ValueError:
        return address


def _trusted_networks() -> list[IPv4Network | IPv6Network]:
    """Parse ``TRUSTED_PROXIES`` into networks; blank and malformed entries skip.

    Malformed entries are rejected at boot (``validate_boot_settings``), so a bad
    one cannot reach a request; the guard here just keeps a stray value from
    turning into a 500.
    """
    networks: list[IPv4Network | IPv6Network] = []
    for entry in settings.trusted_proxies:
        if not entry.strip():
            continue
        try:
            networks.append(ip_network(entry.strip(), strict=False))
        except ValueError:
            continue
    return networks


def _is_trusted(address: str, networks: list[IPv4Network | IPv6Network]) -> bool:
    """Whether ``address`` falls inside one of the trusted proxy networks."""
    try:
        parsed = ip_address(address)
    except ValueError:
        return False
    return any(parsed in network for network in networks)


def _resolved_client_host(request: Request) -> str:
    """The client address to count against, honouring a trusted proxy chain.

    With no trusted proxies configured the peer is returned and the header is
    ignored entirely, so an invented ``X-Forwarded-For`` cannot mint buckets.
    When the peer is a trusted proxy, the header is walked right to left,
    skipping every hop that is itself a trusted proxy: the first address that is
    not one of them is the client the nearest proxy actually saw. If every hop
    is trusted (only proxies in the chain), the leftmost entry — what the first
    proxy recorded — is used.
    """
    peer = request.client.host if request.client else "unknown"
    networks = _trusted_networks()
    if not networks or not _is_trusted(peer, networks):
        return peer

    forwarded = request.headers.get("x-forwarded-for")
    if not forwarded:
        return peer

    hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
    for hop in reversed(hops):
        if not _is_trusted(hop, networks):
            return _normalise(hop)
    return _normalise(hops[0]) if hops else peer


def _client_key(request: Request, scope: str) -> str:
    return f"{scope}:{_resolved_client_host(request)}"


def check_rate_limit(key: str, limit: int, window_seconds: int) -> bool:
    """Record a hit for ``key`` and report whether it is within ``limit``.

    A sliding window is kept as the timestamps of recent hits, so a caller that
    pauses for ``window_seconds`` regains its full allowance instead of waiting
    for a fixed bucket to roll over.
    """
    now = monotonic()
    cutoff = now - window_seconds
    with _lock:
        recent = [hit for hit in _hits.get(key, []) if hit > cutoff]
        if len(recent) >= limit:
            _hits[key] = recent
            return False
        recent.append(now)
        _hits[key] = recent
        return True


def rate_limit(scope: str) -> Callable[[Request], Awaitable[None]]:
    """Build the dependency that enforces the configured window for ``scope``."""

    async def dependency(request: Request) -> None:
        if not settings.rate_limit_enabled:
            return

        limit = settings.rate_limit_requests
        window = settings.rate_limit_window_seconds
        if check_rate_limit(_client_key(request, scope), limit, window):
            return

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded - at most {limit} requests per {window} seconds",
            headers={"Retry-After": str(window)},
        )

    return dependency
