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


class SubmitterAccountNotFoundError(GeoGuardError):
    """The submitter's Stellar account does not exist on the network yet.

    An anchor transaction takes the submitter as its source, so the account must
    already exist on-chain to supply a sequence number. A freshly generated
    wallet is not an account until something funds it, which makes this the
    normal state for a new user rather than a server fault — so it reports 400
    and names the action that resolves it.
    """

    def __init__(self, message: str):
        super().__init__(message, status_code=400)


class HasherError(GeoGuardError):
    """CSV hashing / canonicalization error."""

    pass


class AnomalyDetectionError(GeoGuardError):
    """AI anomaly detection error."""

    pass


class MerkleError(GeoGuardError):
    """Merkle batch construction or inclusion-proof error."""

    pass


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(GeoGuardError)
    async def geoguard_error_handler(request: Request, exc: GeoGuardError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
        )
