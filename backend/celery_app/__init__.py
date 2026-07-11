"""Celery application instance for Memoria background tasks.

Uses Redis (``REDIS_URL`` from settings) as both broker and result backend.
Task modules are eagerly discovered via ``include`` so a worker started with
``-A celery_app`` registers all tasks.
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

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
    beat_schedule={
        # Decay importance of non-core memories daily at 03:00 UTC.
        "decay-memories-daily": {
            "task": "decay_memories_task",
            "schedule": crontab(hour=3, minute=0),
        },
        # Consolidate similar memories weekly on Saturday at 04:00 UTC.
        "consolidate-memories-weekly": {
            "task": "consolidate_memories_task",
            "schedule": crontab(day_of_week=6, hour=4, minute=0),
        },
    },
)

__all__ = ["celery_app"]
