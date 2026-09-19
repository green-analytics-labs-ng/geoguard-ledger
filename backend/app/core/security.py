"""Authentication utilities for the write endpoints.

Uploads and anchoring require an ``X-API-Key`` header whose value matches one of
the keys configured in ``API_KEYS``. With no keys configured, authentication is
disabled — but only in development and only under the explicit
``ALLOW_UNAUTHENTICATED_WRITES=true`` opt-in, so a checkout cannot run open by
accident (see ``validate_boot_settings``).

Verification is deliberately excluded: it is public and permissionless because
that is what makes a proof independently checkable, and it is rate limited
instead (see ``app.core.rate_limit``).
"""

import hmac

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def configured_api_keys() -> list[str]:
    """Return the configured keys, with whitespace and empty entries removed."""
    return [key.strip() for key in settings.api_keys.split(",") if key.strip()]


def _matches(provided: str, expected: str) -> bool:
    """Compare two keys in constant time.

    ``hmac.compare_digest`` is used rather than ``==`` so the time taken does
    not depend on how many leading characters match, which would otherwise leak
    the key one byte at a time. Encoding to bytes keeps non-ASCII input from
    raising inside the comparison.
    """
    return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


def _any_match(provided: str, keys: list[str]) -> bool:
    """Whether ``provided`` matches any of ``keys``, comparing against all of them.

    Every key is compared even after a match, so the running time does not
    reveal which key (or position) succeeded.
    """
    matched = False
    for key in keys:
        matched = _matches(provided, key) or matched
    return matched


async def verify_api_key(api_key: str | None = Security(api_key_header)) -> str:
    """Allow the request when it carries a configured ``X-API-Key``.

    Returns the presented key on success (``"anonymous"`` when authentication is
    disabled and no key was sent). Raises ``401`` when a key is required but
    missing or does not match one of the configured keys.
    """
    keys = configured_api_keys()
    if not keys:
        # Auth disabled (development): the caller is not required to identify.
        return api_key or "anonymous"

    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )

    if not _any_match(api_key, keys):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    return api_key
