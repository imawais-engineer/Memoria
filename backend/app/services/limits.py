"""Per-user rate limiting and daily LLM token caps.

Counters live in Redis (``INCR`` + ``EXPIRE``). If Redis is unreachable the
limiter falls back to process-local in-memory counters, so a Redis outage
degrades to per-process limits instead of failing open or closing the API.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone

from fastapi import Depends, HTTPException

from app.config import get_settings
from app.core.auth import get_current_user

logger = logging.getLogger(__name__)


class MemoryCounterStore:
    """Process-local counters with expiry."""

    def __init__(self) -> None:
        self._data: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()

    def incr(self, key: str, amount: int, ttl: int) -> int:
        now = time.monotonic()
        with self._lock:
            value, expires = self._data.get(key, (0, 0.0))
            if expires <= now:
                value, expires = 0, now + ttl
            value += amount
            self._data[key] = (value, expires)
            return value

    def get(self, key: str) -> int:
        now = time.monotonic()
        with self._lock:
            value, expires = self._data.get(key, (0, 0.0))
            return value if expires > now else 0

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


class Limiter:
    def __init__(self, redis_client=None, fallback: MemoryCounterStore | None = None):
        self.redis = redis_client
        self.fallback = fallback or MemoryCounterStore()

    async def _incr(self, key: str, amount: int, ttl: int) -> int:
        if self.redis is not None:
            try:
                # One round trip, and the TTL is (re)set on every call so a
                # failed first EXPIRE can never leave a key without expiry.
                pipe = self.redis.pipeline(transaction=True)
                pipe.incrby(key, amount)
                pipe.expire(key, ttl)
                results = await pipe.execute()
                return int(results[0])
            except Exception:  # noqa: BLE001
                logger.warning("Redis limiter unavailable, using in-memory", exc_info=True)
        return self.fallback.incr(key, amount, ttl)

    async def _get(self, key: str) -> int:
        if self.redis is not None:
            try:
                return int(await self.redis.get(key) or 0)
            except Exception:  # noqa: BLE001
                logger.warning("Redis limiter unavailable, using in-memory", exc_info=True)
        return self.fallback.get(key)

    async def check_rate(self, user_id: str, limit: int, window: int = 60) -> None:
        """Count one request; raise 429 once ``limit`` per window is exceeded."""

        if limit <= 0:
            return
        bucket = int(time.time() // window)
        count = await self._incr(f"rl:{user_id}:{bucket}", 1, window + 1)
        if count > limit:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please slow down.",
                headers={"Retry-After": str(window)},
            )

    @staticmethod
    def _day_key(user_id: str) -> str:
        return f"tok:{user_id}:{datetime.now(timezone.utc):%Y%m%d}"

    async def check_token_cap(self, user_id: str, cap: int) -> None:
        """Raise 429 if the user already used the daily token budget."""

        if cap <= 0:
            return
        if await self._get(self._day_key(user_id)) >= cap:
            raise HTTPException(status_code=429, detail="Daily token limit reached.")

    async def add_tokens(self, user_id: str, tokens: int) -> int:
        if tokens <= 0:
            return 0
        return await self._incr(self._day_key(user_id), tokens, 2 * 24 * 3600)


def estimate_tokens(*texts: str) -> int:
    """Cheap token estimate (about 4 characters per token)."""

    return sum(max(1, len(t) // 4) for t in texts if t)


_limiter: Limiter | None = None


def get_limiter() -> Limiter:
    global _limiter
    if _limiter is None:
        client = None
        try:
            from app.core.redis_client import redis_client as client
        except Exception:  # noqa: BLE001
            client = None
        _limiter = Limiter(client)
    return _limiter


async def enforce_limits(
    user_id: str = Depends(get_current_user),
    limiter: Limiter = Depends(get_limiter),
) -> str:
    """Dependency for LLM-backed routes: rate limit plus daily token cap."""

    settings = get_settings()
    await limiter.check_rate(user_id, settings.rate_limit_per_min)
    await limiter.check_token_cap(user_id, settings.daily_token_cap)
    return user_id


async def enforce_mcp_limits(user_id: str, limiter: Limiter | None = None) -> None:
    """Rate limit and token cap for MCP tools (same budget as the REST API).

    Raises ``ValueError`` so FastMCP reports it as a tool error.
    """

    limiter = limiter or get_limiter()
    settings = get_settings()
    try:
        await limiter.check_rate(user_id, settings.rate_limit_per_min)
        await limiter.check_token_cap(user_id, settings.daily_token_cap)
    except HTTPException as exc:
        raise ValueError(str(exc.detail)) from exc


async def charge_mcp_tokens(
    user_id: str, tokens: int, limiter: Limiter | None = None
) -> None:
    await (limiter or get_limiter()).add_tokens(user_id, tokens)
