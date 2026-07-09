"""Celery tasks wrapping the async memory pipeline.

Celery workers run synchronously, so each task drives the async ingestion
coroutine via ``asyncio.run`` with a fresh async session.
"""

from __future__ import annotations

import asyncio
import logging

from app.core.database import async_session
from app.memory.consolidation import consolidate_memories
from app.memory.forgetting import apply_decay
from app.memory.ingestion import extract_and_store_memories
from celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="extract_memories_task")
def extract_memories_task(
    conversation_text: str,
    user_id: str,
    message_id: str,
) -> None:
    """Queue-friendly wrapper around :func:`extract_and_store_memories`.

    Called as ``extract_memories_task.delay(conversation_text, user_id,
    message_id)`` after a chat turn to run memory extraction in the background.
    """

    async def _run() -> None:
        async with async_session() as session:
            await extract_and_store_memories(
                conversation_text, user_id, message_id, session
            )

    asyncio.run(_run())


@celery_app.task(name="decay_memories_task")
def decay_memories_task() -> dict[str, int]:
    """Daily (Celery Beat, 03:00 UTC) importance decay + archival."""

    async def _run() -> dict[str, int]:
        async with async_session() as session:
            return await apply_decay(session)

    return asyncio.run(_run())


@celery_app.task(name="consolidate_memories_task")
def consolidate_memories_task() -> dict[str, int]:
    """Weekly (Celery Beat, Sun 04:00 UTC) clustering + summarization."""

    async def _run() -> dict[str, int]:
        async with async_session() as session:
            return await consolidate_memories(session)

    return asyncio.run(_run())
