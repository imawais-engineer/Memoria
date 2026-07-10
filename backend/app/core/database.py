"""Async SQLAlchemy engine, session factory, and session dependency.

This module centralizes database access for the backend. The engine is created
once at import time from the application settings and reused across requests.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

settings = get_settings()

# A single async engine for the whole application. ``echo=False`` keeps SQL
# logging off by default; flip it on temporarily when debugging queries.
engine: AsyncEngine = create_async_engine(settings.database_url, echo=False)

# ``expire_on_commit=False`` lets ORM objects stay usable after ``commit()``
# without triggering a lazy reload (important for async code paths).
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Alias for callers (e.g. Celery tasks) that import ``async_session``.
async_session = AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session, ensuring it is closed afterwards.

    Intended for use as a FastAPI dependency (``Depends(get_db)``) in later
    modules. The ``async with`` block guarantees the session is closed even if
    the caller raises.
    """

    async with AsyncSessionLocal() as session:
        yield session


async def check_connection() -> bool:
    """Open a session and run ``SELECT 1`` to verify connectivity.

    Returns ``True`` when the round-trip succeeds. Call this manually (e.g. from
    a script or the REPL); it is intentionally not wired to a route yet.
    """

    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT 1"))
        return result.scalar_one() == 1
