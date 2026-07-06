"""Custom exception handlers for the FastAPI application."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class GeoGuardError(Exception):
    """Base exception for GeoGuard Ledger."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code


class ContractError(GeoGuardError):
    """Soroban contract interaction error."""
    pass


class HasherError(GeoGuardError):
    """CSV hashing / canonicalization error."""
    pass


class AnomalyDetectionError(GeoGuardError):
    """AI anomaly detection error."""
    pass


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(GeoGuardError)
    async def geoguard_error_handler(request: Request, exc: GeoGuardError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
        )
