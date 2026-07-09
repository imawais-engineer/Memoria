"""Core chat agent orchestration.

``handle_message`` ties together short-term session memory (Redis), long-term
memory retrieval (pgvector), the Qwen chat model, and background memory
ingestion (Celery).
"""

from __future__ import annotations

import json
import logging
import uuid

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dashscope_client import call_qwen_chat
from app.memory.retrieval import retrieve_context

logger = logging.getLogger(__name__)

# Chat model (per roadmap Module 6).
CHAT_MODEL = "qwen-plus"

# Keep only the most recent N messages of session history in Redis.
SESSION_MAX_MESSAGES = 10

# Session state expires after this many seconds of inactivity (7 days).
SESSION_TTL_SECONDS = 7 * 24 * 60 * 60

SYSTEM_PROMPT_TEMPLATE = (
    "You are a personal AI with memory. Here is what you know about the user: "
    "{memory_context}. Use this to personalise responses."
)


async def handle_message(
    user_id: str,
    user_message: str,
    session_id: str | None = None,
    *,
    db_session: AsyncSession,
    redis_client: redis.Redis,
) -> dict:
    """Handle one chat turn and return ``{"reply": ..., "session_id": ...}``.

    ``db_session`` and ``redis_client`` are injected (from FastAPI dependencies).
    """

    if not session_id:
        session_id = str(uuid.uuid4())

    session_key = f"session:{session_id}"

    # 1. Load recent session history (list of {role, content}).
    raw_history = await redis_client.lrange(session_key, -SESSION_MAX_MESSAGES, -1)
    history: list[dict] = []
    for item in raw_history:
        try:
            history.append(json.loads(item))
        except (json.JSONDecodeError, TypeError):
            continue

    # 2. Retrieve long-term memory context.
    memory_context = await retrieve_context(
        user_id, user_message, max_tokens=6000, db_session=db_session
    )

    # 3-4. Build the message list: system prompt + history + current message.
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(memory_context=memory_context)
    messages = (
        [{"role": "system", "content": system_prompt}]
        + history
        + [{"role": "user", "content": user_message}]
    )

    # 5. Call Qwen for the assistant reply.
    reply = await call_qwen_chat(messages, model=CHAT_MODEL)

    # 6. Persist the exchange to Redis, trimmed to the last N messages.
    await redis_client.rpush(
        session_key,
        json.dumps({"role": "user", "content": user_message}),
        json.dumps({"role": "assistant", "content": reply}),
    )
    await redis_client.ltrim(session_key, -SESSION_MAX_MESSAGES, -1)
    await redis_client.expire(session_key, SESSION_TTL_SECONDS)

    # 7. Fire-and-forget background memory extraction from this exchange.
    message_id = str(uuid.uuid4())
    conversation_text = f"User: {user_message}\nAssistant: {reply}"
    try:
        from celery_app.tasks import extract_memories_task

        extract_memories_task.delay(
            conversation_text=conversation_text,
            user_id=user_id,
            message_id=message_id,
        )
    except Exception:  # noqa: BLE001 - enqueue failure must not break the reply
        logger.exception("Failed to enqueue extract_memories_task")

    return {"reply": reply, "session_id": session_id}
