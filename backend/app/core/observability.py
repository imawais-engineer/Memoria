"""Readiness checks and a tiny Prometheus text-format metrics registry.

No third party dependency: counters are kept in process memory, so with several
uvicorn workers each process reports its own numbers (scrape every instance).
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections import defaultdict

from sqlalchemy import text

CHECK_TIMEOUT_SECONDS = 3.0


async def check_database() -> None:
    """Raise if ``SELECT 1`` fails against the configured database."""

    from app.core.database import engine

    async def _run() -> None:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    await asyncio.wait_for(_run(), CHECK_TIMEOUT_SECONDS)


async def check_redis() -> None:
    """Raise if Redis does not answer ``PING``."""

    from app.core.redis_client import redis_client

    await asyncio.wait_for(redis_client.ping(), CHECK_TIMEOUT_SECONDS)


async def run_readiness_checks() -> dict[str, str]:
    """Return ``{"database": "ok"|"error", "redis": ...}`` without raising.

    Error details are not returned, since they can contain hostnames or DSNs.
    """

    results: dict[str, str] = {}
    for name, check in (("database", check_database), ("redis", check_redis)):
        try:
            await check()
            results[name] = "ok"
        except Exception:
            results[name] = "error"
    return results


class Metrics:
    """Minimal thread-safe request counters and latency sums."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests: dict[tuple[str, str, str], int] = defaultdict(int)
        self._duration_sum: dict[tuple[str, str], float] = defaultdict(float)
        self._duration_count: dict[tuple[str, str], int] = defaultdict(int)
        self.started_at = time.time()

    def observe(self, method: str, path: str, status: int, seconds: float) -> None:
        with self._lock:
            self._requests[(method, path, str(status))] += 1
            self._duration_sum[(method, path)] += seconds
            self._duration_count[(method, path)] += 1

    @staticmethod
    def _esc(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

    def render(self) -> str:
        lines = [
            "# HELP memoria_http_requests_total HTTP requests by method, route and status.",
            "# TYPE memoria_http_requests_total counter",
        ]
        with self._lock:
            for (method, path, status), n in sorted(self._requests.items()):
                lines.append(
                    f'memoria_http_requests_total{{method="{self._esc(method)}",'
                    f'path="{self._esc(path)}",status="{status}"}} {n}'
                )
            lines += [
                "# HELP memoria_http_request_duration_seconds Request latency (sum and count).",
                "# TYPE memoria_http_request_duration_seconds summary",
            ]
            for (method, path), total in sorted(self._duration_sum.items()):
                labels = f'method="{self._esc(method)}",path="{self._esc(path)}"'
                lines.append(f"memoria_http_request_duration_seconds_sum{{{labels}}} {total:.6f}")
                count = self._duration_count[(method, path)]
                lines.append(f"memoria_http_request_duration_seconds_count{{{labels}}} {count}")
        lines += [
            "# HELP memoria_uptime_seconds Seconds since process start.",
            "# TYPE memoria_uptime_seconds gauge",
            f"memoria_uptime_seconds {time.time() - self.started_at:.1f}",
        ]
        return "\n".join(lines) + "\n"


metrics = Metrics()
