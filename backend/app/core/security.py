"""Authentication and security utilities.

Phase 1: Simple API key validation.
Phase 3+: JWT/OAuth integration.
"""

from fastapi.security import APIKeyHeader, Security

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """Verify the API key from the request header.

    In Phase 1, this is a placeholder. In Phase 3+, this validates
    against a database of registered researchers or JWT tokens.
    """
    # TODO: Implement proper API key validation
    return api_key or "anonymous"
