"""Test fixtures and configuration for backend tests.

Uses an in-memory SQLite database (aiosqlite) for isolated test DB state
and mocks the Soroban RPC client to avoid external network calls.
"""

from collections.abc import AsyncGenerator
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.services.hasher import compute_hash as _compute_hash

# Use aiosqlite for isolated, fast test database
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(autouse=True)
async def setup_database() -> AsyncGenerator[None, None]:
    """Create all tables before each test and drop them after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    """Override the FastAPI dependency to use the test database."""
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture
def app():
    """Create a fresh FastAPI app with test DB overrides."""
    application = create_app()
    application.dependency_overrides[get_db] = override_get_db
    return application


@pytest.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Sample CSV data ───────────────────────────────────────────────

SAMPLE_CSV = """sample_id,latitude,longitude,pH,conductivity,dissolved_oxygen,temperature
S001,34.052200,-118.243700,7.20,450.00,8.50,22.10
S002,34.052500,-118.244000,7.15,452.00,8.30,22.30
S003,34.052800,-118.244300,7.18,448.00,8.70,22.00
S004,34.053100,-118.244600,7.22,455.00,8.40,22.20
S005,34.053400,-118.244900,7.19,449.00,8.60,22.40
"""

ANOMALOUS_CSV = """sample_id,latitude,longitude,pH,conductivity,dissolved_oxygen,temperature
S001,34.052200,-118.243700,7.20,450.00,8.50,22.10
S002,34.052500,-118.244000,7.15,452.00,8.30,22.30
S003,34.052800,-118.244300,7.18,448.00,8.70,22.00
S004,34.053100,-118.244600,7.22,455.00,8.40,22.20
S005,34.053400,-118.244900,7.19,449.00,8.60,22.40
S006,34.050000,-118.250000,9.99,9999.00,0.10,999.99
"""

SAMPLE_HASH = _compute_hash(SAMPLE_CSV)


# ── Mock Soroban responses ────────────────────────────────────────

MOCK_TX_HASH = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b"
MOCK_LEDGER = 1234567


@pytest.fixture
def mock_build_transaction():
    """Mock the Soroban transaction builder to return a fake XDR."""
    with patch("app.api.v1.datasets.build_anchor_transaction") as mock:
        mock.return_value = "AAAAAgAAAABbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        yield mock


@pytest.fixture
def mock_submit_transaction():
    """Mock the Soroban transaction submitter to return success."""
    with patch("app.api.v1.datasets.submit_transaction") as mock:
        mock.return_value = {
            "tx_hash": MOCK_TX_HASH,
            "ledger": MOCK_LEDGER,
        }
        yield mock


@pytest.fixture
def mock_submit_transaction_failure():
    """Mock the Soroban transaction submitter to raise an error."""
    with patch("app.api.v1.datasets.submit_transaction") as mock:
        mock.side_effect = RuntimeError("Soroban RPC error")
        yield mock


@pytest.fixture
def mock_verify_on_chain_found():
    """Mock the Soroban verifier to return an on-chain record."""
    with patch("app.api.v1.verify.verify_on_chain") as mock:
        mock.return_value = {
            "dataset_hash": SAMPLE_HASH,
            "anomaly_score": 0,
            "model_version": "isoforest_v1",
            "timestamp": 1751715300,
            "submitter": "GABCDEF123456789012345678901234567890123",
        }
        yield mock


@pytest.fixture
def mock_verify_on_chain_not_found():
    """Mock the Soroban verifier to return None (not on-chain)."""
    with patch("app.api.v1.verify.verify_on_chain") as mock:
        mock.return_value = None
        yield mock
