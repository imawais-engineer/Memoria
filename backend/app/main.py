"""FastAPI application entrypoint for the Memoria backend.

Module 1 intentionally ships only a health check endpoint; database, Redis,
Celery and DashScope wiring are added in later modules.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import __version__
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.feedback import router as feedback_router
from app.api.memories import router as memories_router
from app.api.sessions import router as sessions_router
from app.config import Settings, get_settings
from app.core.database import get_db  # noqa: F401  (exposed for later routes)
from app.mcp.memory_skill import MEMORY_TOOL_CATALOG


class HealthResponse(BaseModel):
    """Response payload for the ``/health`` endpoint."""

    status: str
    service: str
    version: str


def create_app() -> FastAPI:
    """Build and configure the FastAPI application instance."""

    settings: Settings = get_settings()

    application = FastAPI(
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
    application.include_router(memories_router)
    application.include_router(sessions_router)

    return application


app = create_app()
