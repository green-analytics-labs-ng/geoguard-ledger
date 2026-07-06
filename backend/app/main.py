"""GeoGuard Ledger — FastAPI application factory."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from logging import getLogger

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import datasets, health, verify
from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.db.base import Base
from app.db.session import async_engine

logger = getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown events."""
    # Startup: create tables if they don't exist
    logger.info("Creating database tables (if not exist)...")
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ready.")

    yield

    # Shutdown: dispose of the database connection pool
    await async_engine.dispose()
    logger.info("Database connection pool disposed.")


def create_app() -> FastAPI:
    app = FastAPI(
        title="GeoGuard Ledger API",
        description="Research integrity system for geochemical data anchoring on Stellar",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(datasets.router, prefix="/api/v1", tags=["datasets"])
    app.include_router(verify.router, prefix="/api/v1", tags=["verify"])

    register_exception_handlers(app)

    return app


app = create_app()
