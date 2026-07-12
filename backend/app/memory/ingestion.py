"""Memory ingestion pipeline.

Extracts structured memories from a conversation turn using Qwen function
calling, embeds each memory with DashScope's text-embedding model, and stores
them in the database. Kept as a plain async function (no Celery task yet).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dashscope_client import (
    DEFAULT_EMBEDDING_MODEL,
    call_qwen_with_functions,
    get_embedding,
)
from app.memory.conflict_detection import detect_conflicts, resolve_conflict
from app.memory.models import Memory
from app.models.chat_session import ChatSession  # noqa: F401  (register FK table)

logger = logging.getLogger(__name__)

# Model used for memory extraction (per roadmap Module 3).
QWEN_MODEL = "qwen-plus"

# Embedding model used to vectorize each extracted memory.
EMBEDDING_MODEL = DEFAULT_EMBEDDING_MODEL

SYSTEM_PROMPT = (
    "You are a memory extraction assistant. Extract factual memories from the "
    "conversation."
)

# Decay rate applied per memory type (core memories never decay).
DECAY_RATES: dict[str, float] = {
    "core": 0.0,
    "semantic": 0.01,
    "episodic": 0.02,
    "procedural": 0.005,
}
DEFAULT_DECAY_RATE = 0.01
CONFLICT_IMPORTANCE_BOOST = 0.1
AUTO_CONFLICT_RESOLUTION = "auto_superseded_on_ingestion"

# Tool/function definition passed to Qwen, matching the roadmap schema.
EXTRACT_MEMORIES_TOOL: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "extract_memories",
            "description": (
                "Extract durable, factual memories about the user from the "
                "conversation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "memories": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "content": {
                                    "type": "string",
                                    "description": "The memory text.",
                                },
                                "type": {
                                    "type": "string",
                                    "enum": [
                                        "core",
                                        "episodic",
                                        "semantic",
                                        "procedural",
                                    ],
                                },
                                "importance": {
                                    "type": "number",
                                    "description": "Importance from 0 to 1.",
                                },
                                "expires_in_hours": {
                                    "type": "number",
                                    "description": "0 means the memory never expires.",
                                },
                            },
                            "required": [
                                "content",
                                "type",
                                "importance",
                                "expires_in_hours",
                            ],
                        },
                    }
                },
                "required": ["memories"],
            },
        },
    }
]


def _extract_tool_arguments(response: Any) -> dict[str, Any] | None:
    """Pull the ``extract_memories`` tool-call arguments from a Qwen response.

    Returns the parsed arguments dict, or ``None`` if the model did not emit a
    tool call.
    """

    try:
        message = response.output["choices"][0]["message"]
    except (KeyError, IndexError, TypeError):
        logger.warning("Unexpected Qwen response shape; no choices/message found.")
        return None

    tool_calls = message.get("tool_calls") if isinstance(message, dict) else None
    if not tool_calls:
        return None

    raw_arguments = tool_calls[0].get("function", {}).get("arguments")
    if not raw_arguments:
        return None

    if isinstance(raw_arguments, str):
        try:
            return json.loads(raw_arguments)
        except json.JSONDecodeError:
            logger.warning("Failed to JSON-decode tool-call arguments.")
            return None
    return raw_arguments


async def extract_and_store_memories(
    conversation_text: str,
    user_id: str,
    message_id: str,
    db_session: AsyncSession,
    session_id: str | None = None,
) -> list[Memory]:
    """Extract memories from a conversation turn and persist them.

    Returns the list of created :class:`Memory` rows (empty if none were
    extracted). Rolls back and re-raises on database errors.
    """

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": conversation_text},
    ]

    response = await call_qwen_with_functions(
        messages, EXTRACT_MEMORIES_TOOL, model=QWEN_MODEL
    )

    arguments = _extract_tool_arguments(response)
    if not arguments:
        logger.info("No memories extracted for message_id=%s", message_id)
        return []

    memory_items = arguments.get("memories") or []
    if not memory_items:
        logger.info("Empty memories array for message_id=%s", message_id)
        return []

    created: list[Memory] = []
    session_uuid = None
    if session_id:
        try:
            from uuid import UUID

            session_uuid = UUID(session_id)
        except ValueError:
            session_uuid = None

    try:
        for item in memory_items:
            content = item.get("content")
            if not content:
                continue

            mem_type = item.get("type", "semantic")
            importance = float(item.get("importance", 0.5))
            expires_in_hours = float(item.get("expires_in_hours", 0) or 0)

            embedding = await get_embedding(content, model=EMBEDDING_MODEL)

            decay_rate = DECAY_RATES.get(mem_type, DEFAULT_DECAY_RATE)
            now = datetime.now(timezone.utc)
            expires_at = (
                now + timedelta(hours=expires_in_hours)
                if expires_in_hours > 0
                else None
            )

            memory = Memory(
                user_id=user_id,
                type=mem_type,
                content=content,
                embedding=embedding,
                importance=importance,
                created_at=now,
                last_accessed=now,
                expires_at=expires_at,
                decay_rate=decay_rate,
                session_id=session_uuid,
                meta_data={"source_message_id": message_id},
            )
            db_session.add(memory)
            await db_session.flush()

            conflicts = await detect_conflicts(
                db_session,
                user_id,
                content,
                exclude_memory_id=memory.id,
            )
            if conflicts:
                logger.warning(
                    "Memory conflict detected for user_id=%s new_memory_id=%s "
                    "conflicting_ids=%s",
                    user_id,
                    memory.id,
                    [str(conflict.id) for conflict in conflicts],
                )
                memory.importance = min(1.0, importance + CONFLICT_IMPORTANCE_BOOST)
                for conflict in conflicts:
                    await resolve_conflict(
                        db_session,
                        str(conflict.id),
                        str(memory.id),
                        AUTO_CONFLICT_RESOLUTION,
                    )

            created.append(memory)

        await db_session.commit()
    except Exception:
        logger.exception(
            "Failed to store memories for message_id=%s; rolling back.", message_id
        )
        await db_session.rollback()
        raise

    logger.info(
        "Stored %d memories for user_id=%s message_id=%s",
        len(created),
        user_id,
        message_id,
    )
    return created
