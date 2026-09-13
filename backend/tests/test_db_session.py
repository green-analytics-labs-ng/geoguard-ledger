"""Tests for the async database session lifecycle.

Every request that depends on `get_db` gets its own session, and the teardown
half of that generator is what hands the connection back to the pool. A
generator that yields but never closes leaks one connection per request until
the pool is exhausted, so these tests pin the teardown rather than only the
setup.
"""

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.db.session as session_module
from app.db.session import AsyncSessionLocal, async_engine, get_db


def test_session_factory_is_configured_for_request_scoped_use() -> None:
    """The factory binds to the app engine and keeps rows usable after commit."""
    assert AsyncSessionLocal.kw["bind"] is async_engine
    assert AsyncSessionLocal.class_ is AsyncSession
    # `expire_on_commit=False` keeps a row's attributes loaded after a commit,
    # so a handler can still serialize the record it just wrote.
    assert AsyncSessionLocal.kw["expire_on_commit"] is False


async def test_get_db_yields_an_active_session() -> None:
    """Dependency injection receives a live AsyncSession."""
    generator: AsyncGenerator[AsyncSession, None] = get_db()
    session = await anext(generator)
    try:
        assert isinstance(session, AsyncSession)
        assert session.is_active is True
    finally:
        await generator.aclose()


async def test_get_db_releases_its_connection_when_the_request_ends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Closing the generator must check the connection back into the pool."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'sessions.db'}")
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(session_module, "AsyncSessionLocal", factory)

    generator = get_db()
    session = await anext(generator)
    try:
        # A session only takes a connection once it actually runs something.
        await session.execute(text("SELECT 1"))
        assert engine.pool.checkedout() == 1
    finally:
        await generator.aclose()

    assert engine.pool.checkedout() == 0
    await engine.dispose()


async def test_get_db_hands_out_a_distinct_session_per_call() -> None:
    """Concurrent requests must not share one session object."""
    first = get_db()
    second = get_db()
    session_a = await anext(first)
    session_b = await anext(second)
    try:
        assert session_a is not session_b
    finally:
        await first.aclose()
        await second.aclose()
