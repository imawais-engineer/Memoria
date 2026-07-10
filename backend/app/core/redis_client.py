"""Async Redis client for session state.

A single global connection pool is created from ``REDIS_URL``. ``decode_responses``
is enabled so values come back as ``str`` rather than ``bytes``.
"""

from __future__ import annotations

import redis.asyncio as redis

from app.config import get_settings

settings = get_settings()

redis_client: redis.Redis = redis.from_url(
    settings.redis_url,
    decode_responses=True,
)


async def get_redis() -> redis.Redis:
    """Return the shared async Redis client (FastAPI dependency)."""

    return redis_client
