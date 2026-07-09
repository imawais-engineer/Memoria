"""Celery application instance for Memoria background tasks.

Uses Redis (``REDIS_URL`` from settings) as both broker and result backend.
Task modules are eagerly discovered via ``include`` so a worker started with
``-A celery_app`` registers all tasks.
"""

from __future__ import annotations

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "memoria",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["celery_app.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

__all__ = ["celery_app"]
