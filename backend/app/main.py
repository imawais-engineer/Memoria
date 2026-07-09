"""FastAPI application entrypoint for the Memoria backend.

Module 1 intentionally ships only a health check endpoint; database, Redis,
Celery and DashScope wiring are added in later modules.
"""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from app import __version__
from app.config import Settings, get_settings


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

    @application.get("/health", response_model=HealthResponse, tags=["system"])
    async def health() -> HealthResponse:
        """Lightweight liveness probe.

        Returns ``200`` with basic service metadata. Touching ``settings``
        ensures configuration loads correctly at request time without leaking
        any secret values in the response.
        """

        _ = settings  # configuration is loaded/validated at startup
        return HealthResponse(status="ok", service="memoria", version=__version__)

    return application


app = create_app()
