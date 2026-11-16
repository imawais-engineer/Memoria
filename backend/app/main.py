"""FastAPI application entrypoint for the Memoria backend.

Module 1 intentionally ships only a health check endpoint; database, Redis,
Celery and DashScope wiring are added in later modules.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import hmac
import time

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import __version__
from app.api.archive import router as archive_router
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.contact_feedback import router as contact_feedback_router
from app.api.feedback import router as feedback_router
from app.api.generate import router as generate_router
from app.api.memorize import router as memorize_router
from app.api.memories import router as memories_router
from app.api.sessions import router as sessions_router
from app.api.tasks import router as tasks_router
from app.config import Settings, get_settings, is_dev, validate_runtime_settings
from app.core.database import engine, get_db  # noqa: F401  (exposed for later routes)
from app.core.llm.dimcheck import check_embedding_dim
from app.core import observability
from app.mcp.memory_skill import MEMORY_TOOL_CATALOG
from app.mcp.server import mount_mcp


class HealthResponse(BaseModel):
    """Response payload for the ``/health`` endpoint."""

    status: str
    service: str
    version: str


READY_CACHE_SECONDS = 2.0
_ready_cache: dict[str, tuple[float, dict[str, str]]] = {}


def create_app() -> FastAPI:
    """Build and configure the FastAPI application instance."""

    settings: Settings = get_settings()
    validate_runtime_settings(settings)

    @asynccontextmanager
    async def lifespan(app_: FastAPI) -> AsyncIterator[None]:
        await check_embedding_dim(engine, settings.embedding_dim)
        async with app_.state.mcp_server.session_manager.run():
            yield

    application = FastAPI(
        lifespan=lifespan,
        title="Memoria",
        version=__version__,
        summary="Personal AI with long-term memory (Qwen Cloud Hackathon).",
    )

    # Permissive CORS for local development (the frontend also proxies via Vite).
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get("/health", response_model=HealthResponse, tags=["system"])
    async def health() -> HealthResponse:
        """Lightweight liveness probe.

        Returns ``200`` with basic service metadata. Touching ``settings``
        ensures configuration loads correctly at request time without leaking
        any secret values in the response.
        """

        _ = settings  # configuration is loaded/validated at startup
        return HealthResponse(status="ok", service="memoria", version=__version__)

    @application.middleware("http")
    async def record_metrics(request: Request, call_next):  # type: ignore[no-untyped-def]
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            route = request.scope.get("route")
            # Use the route template to keep label cardinality bounded.
            path = getattr(route, "path", None) or "unmatched"
            observability.metrics.observe(
                request.method, path, status, time.perf_counter() - start
            )

    @application.get("/health/ready", tags=["system"])
    async def health_ready(response: Response) -> dict[str, object]:
        """Readiness probe: ``200`` only when Postgres and Redis both respond.

        The result is cached briefly so anonymous callers cannot turn the probe
        into a load generator against Postgres and Redis.
        """

        now = time.monotonic()
        cached = _ready_cache.get("v")
        if cached and now - cached[0] < READY_CACHE_SECONDS:
            checks = cached[1]
        else:
            checks = await observability.run_readiness_checks()
            _ready_cache["v"] = (now, checks)
        ready = all(v == "ok" for v in checks.values())
        if not ready:
            response.status_code = 503
        return {"status": "ready" if ready else "unavailable", "checks": checks}

    @application.get("/metrics", tags=["system"], include_in_schema=False)
    async def metrics_endpoint(request: Request) -> Response:
        """Prometheus text exposition, guarded by ``METRICS_TOKEN``."""

        settings = get_settings()
        if settings.metrics_token:
            supplied = request.headers.get("authorization", "")
            if not hmac.compare_digest(
                supplied.encode(), f"Bearer {settings.metrics_token}".encode()
            ):
                raise HTTPException(status_code=401, detail="Metrics token required")
        elif not is_dev(settings):
            raise HTTPException(
                status_code=403, detail="Set METRICS_TOKEN to enable /metrics"
            )

        return Response(
            observability.metrics.render(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    @application.get("/mcp/memory-skills", tags=["mcp"])
    async def memory_skills() -> dict[str, list[dict[str, str]]]:
        """Expose memory operations as MCP tools for Qwen."""

        return {
            "tools": [
                {"name": tool["name"], "description": tool["description"]}
                for tool in MEMORY_TOOL_CATALOG
            ]
        }

    application.include_router(auth_router)
    application.include_router(chat_router)
    application.include_router(feedback_router)
    application.include_router(contact_feedback_router)
    application.include_router(generate_router)
    application.include_router(memorize_router)
    application.include_router(memories_router)
    application.include_router(archive_router)
    application.include_router(sessions_router)
    application.include_router(tasks_router)
    mount_mcp(application)

    return application


app = create_app()
