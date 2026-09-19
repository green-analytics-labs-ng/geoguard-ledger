"""A small in-process rate limiter for the endpoints that do real work.

Both the dataset upload and the verification file mode parse and hash a file,
and verification also queries the Soroban RPC — work a caller could otherwise
repeat without limit. This bounds it per client IP over a sliding window.

The counters live in the process, so this guards against one abusive client
rather than acting as a distributed quota: behind several workers each process
tracks its own window, and a restart clears them. That is an acceptable Phase 1
trade-off; a shared store (e.g. Redis) can replace the storage without changing
the call sites.
"""

from collections.abc import Awaitable, Callable
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


def _client_key(request: Request, scope: str) -> str:
    client = request.client.host if request.client else "unknown"
    return f"{scope}:{client}"


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
