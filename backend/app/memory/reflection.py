"""Reflective memory layer: synthesize high-level user insights from stored facts.

Periodically analyzes active memories and persists a concise reflection as a
high-importance semantic memory for future personalization.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dashscope_client import call_qwen_chat, get_embedding
from app.memory.models import Memory

logger = logging.getLogger(__name__)

REFLECTION_MODEL = "qwen-plus"
MIN_MEMORIES_FOR_REFLECTION = 5
REFLECTION_IMPORTANCE = 9.0
REFLECTION_DECAY_RATE = 0.01

REFLECTION_PROMPT = (
    "Based on these memories about the user, write 2-3 sentences that capture "
    "their key preferences, values, or recurring patterns. This reflection will "
    "be stored and used to personalise future interactions."
)


async def generate_user_reflection(user_id: str, db_session: AsyncSession) -> str:
    """Analyze active memories and store a new reflective semantic memory.

    Returns the generated reflection text, or an empty string when there is
    insufficient data or generation fails.
    """

    try:
        stmt = (
            select(Memory)
            .where(
                Memory.user_id == user_id,
                Memory.archived.is_(False),
                Memory.superseded.is_(False),
            )
            .order_by(Memory.created_at.asc())
        )
        memories = list((await db_session.execute(stmt)).scalars().all())

        if len(memories) < MIN_MEMORIES_FOR_REFLECTION:
            logger.info(
                "Skipping reflection for user_id=%s: only %d memories",
                user_id,
                len(memories),
            )
            return ""

        memory_lines = "\n".join(f"- {memory.content}" for memory in memories)
        messages = [
            {"role": "system", "content": REFLECTION_PROMPT},
            {
                "role": "user",
                "content": f"Memories about the user:\n{memory_lines}",
            },
        ]
        reflection_text = (await call_qwen_chat(messages, model=REFLECTION_MODEL)).strip()
        if not reflection_text:
            return ""

        embedding = await get_embedding(reflection_text)
        now = datetime.now(timezone.utc)
        db_session.add(
            Memory(
                user_id=user_id,
                type="semantic",
                content=reflection_text,
                embedding=embedding,
                importance=REFLECTION_IMPORTANCE,
                created_at=now,
                last_accessed=now,
                decay_rate=REFLECTION_DECAY_RATE,
                meta_data={"source": "reflection"},
            )
        )
        await db_session.commit()
        logger.info("Stored reflection for user_id=%s", user_id)
        return reflection_text
    except Exception:
        logger.exception("generate_user_reflection failed for user_id=%s", user_id)
        await db_session.rollback()
        return ""


async def get_latest_reflection(user_id: str, db_session: AsyncSession) -> str:
    """Return the most recent reflection memory content for ``user_id``."""

    stmt = (
        select(Memory)
        .where(
            Memory.user_id == user_id,
            Memory.archived.is_(False),
            Memory.superseded.is_(False),
            Memory.meta_data["source"].astext == "reflection",
        )
        .order_by(Memory.created_at.desc())
        .limit(1)
    )
    memory = (await db_session.execute(stmt)).scalar_one_or_none()
    return memory.content if memory else ""
