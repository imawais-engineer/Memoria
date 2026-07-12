"""Celery tasks wrapping the async memory pipeline.

Celery workers run synchronously, so each task drives the async ingestion
coroutine via ``asyncio.run`` with a fresh async session.
"""

from __future__ import annotations

import asyncio
import logging

from app.core.database import async_session
from app.memory.consolidation import consolidate_memories, fetch_active_user_ids
from app.memory.forgetting import apply_decay
from app.memory.ingestion import extract_and_store_memories
from celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro_factory):
    """Run an async coroutine factory under ``asyncio.run`` and dispose the engine.

    Celery workers invoke tasks synchronously; disposing the shared async engine
    after each run avoids asyncpg connections being bound to a closed event loop
    on subsequent invocations.
    """

    from app.core.database import engine

    async def _wrapped():
        try:
            return await coro_factory()
        finally:
            await engine.dispose()

    return asyncio.run(_wrapped())


@celery_app.task(name="extract_memories_task")
def extract_memories_task(
    conversation_text: str,
    user_id: str,
    message_id: str,
    session_id: str | None = None,
    is_memoryless: bool = False,
) -> None:
    """Queue-friendly wrapper around :func:`extract_and_store_memories`.

    Called as ``extract_memories_task.delay(conversation_text, user_id,
    message_id)`` after a chat turn to run memory extraction in the background.
    """

    async def _run() -> None:
        async with async_session() as session:
            await extract_and_store_memories(
                conversation_text,
                user_id,
                message_id,
                session,
                session_id,
                is_memoryless,
            )

    _run_async(_run)


@celery_app.task(name="decay_memories_task")
def decay_memories_task() -> dict[str, int]:
    """Daily (Celery Beat, 03:00 UTC) importance decay + archival."""

    async def _run() -> dict[str, int]:
        async with async_session() as session:
            return await apply_decay(session)

    return _run_async(_run)


@celery_app.task(name="consolidate_memories_task")
def consolidate_memories_task() -> dict[str, int]:
    """Weekly (Celery Beat, Sat 04:00 UTC) clustering + summarization per user."""

    async def _run() -> dict[str, int]:
        user_ids = await fetch_active_user_ids()
        total_summaries = 0
        for user_id in user_ids:
            total_summaries += await consolidate_memories(user_id)

        logger.info(
            "Consolidation complete: %d users, %d total summaries",
            len(user_ids),
            total_summaries,
        )
        return {"users_processed": len(user_ids), "total_summaries": total_summaries}

    return _run_async(_run)
