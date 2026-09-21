"""GeoGuard Ledger — FastAPI application factory."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from logging import getLogger

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import batches, datasets, health, maintenance, verify
from app.config import settings, validate_boot_settings
from app.core.exceptions import register_exception_handlers
from app.db.session import async_engine

logger = getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown events."""
    # The schema belongs to Alembic, and migrations are applied before the
    # server starts (see the Dockerfile's command). Creating tables here would
    # leave them with no recorded revision, so `alembic upgrade head` would then
    # refuse to touch a database that already looks non-empty — which is a worse
    # failure than the missing-table error this avoids.
    yield

    # Shutdown: dispose of the database connection pool
    await async_engine.dispose()
    logger.info("Database connection pool disposed.")


def create_app() -> FastAPI:
    # Fail at construction rather than at the first request: a deployment that
    # is missing its contract, auth key, or CORS origin must not come up at all.
    validate_boot_settings()

    app = FastAPI(
        title="GeoGuard Ledger API",
        description="Research integrity system for geochemical data anchoring on Stellar",
        version="0.3.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api_cors_origins,
        allow_credentials=True,
        allow_methods=settings.api_cors_methods,
        allow_headers=settings.api_cors_headers,
    )

    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(datasets.router, prefix="/api/v1", tags=["datasets"])
    app.include_router(batches.router, prefix="/api/v1", tags=["batches"])
    app.include_router(verify.router, prefix="/api/v1", tags=["verify"])
    app.include_router(maintenance.router, prefix="/api/v1", tags=["maintenance"])

    register_exception_handlers(app)

    return app


app = create_app()
