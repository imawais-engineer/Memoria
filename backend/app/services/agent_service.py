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

from app.core.dashscope_client import call_qwen_chat, get_embedding
from app.memory.models import Memory
from app.memory.retrieval import retrieve_context

logger = logging.getLogger(__name__)

# Chat model (per roadmap Module 6).
CHAT_MODEL = "qwen-plus"

# Keep only the most recent N messages of session history in Redis.
SESSION_MAX_MESSAGES = 10

# Session state expires after this many seconds of inactivity (7 days).
SESSION_TTL_SECONDS = 7 * 24 * 60 * 60

# Regenerate the rolling session summary every N turns (or on explicit recap).
SUMMARY_EVERY_N_TURNS = 5

# Importance/decay for a persisted session-summary memory.
SESSION_SUMMARY_IMPORTANCE = 0.7
SESSION_SUMMARY_DECAY_RATE = 0.02

# Substrings that trigger an on-demand recap/summary.
RECAP_KEYWORDS = ("recap", "summar", "remind me")

SYSTEM_PROMPT_TEMPLATE = (
    "You are a personal AI with memory. Here is what you know about the user: "
    "{memory_context}. Use this to personalise responses."
)


def _wants_recap(message: str) -> bool:
    """Return True if the user is explicitly asking for a recap/summary."""

    lowered = message.lower()
    return any(keyword in lowered for keyword in RECAP_KEYWORDS)


async def _generate_session_summary(
    history: list[dict],
    session_key: str,
    redis_client: redis.Redis,
) -> str:
    """Summarize recent turns via Qwen and cache it in Redis."""

    conversation = "\n".join(f"{m['role']}: {m['content']}" for m in history)
    messages = [
        {
            "role": "system",
            "content": (
                "Summarize the conversation below in 2-3 concise sentences, "
                "focusing on durable facts about the user and the main topics "
                "discussed. Respond with only the summary."
            ),
        },
        {"role": "user", "content": conversation},
    ]
    summary = (await call_qwen_chat(messages, model=CHAT_MODEL)).strip()
    await redis_client.set(
        f"{session_key}:summary", summary, ex=SESSION_TTL_SECONDS
    )
    return summary


async def _store_summary_memory(
    summary: str,
    user_id: str,
    session_id: str,
    db_session: AsyncSession,
) -> None:
    """Persist the session summary as an episodic memory for cross-session recall."""

    embedding = await get_embedding(summary)
    db_session.add(
        Memory(
            user_id=user_id,
            type="episodic",
            content=summary,
            embedding=embedding,
            importance=SESSION_SUMMARY_IMPORTANCE,
            decay_rate=SESSION_SUMMARY_DECAY_RATE,
            meta_data={"kind": "session_summary", "session_id": session_id},
        )
    )
    await db_session.commit()


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
    # Prepend the rolling session summary (if any) so context survives trimming.
    session_summary = await redis_client.get(f"{session_key}:summary")
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(memory_context=memory_context)
    if session_summary:
        system_prompt = (
            f"Summary of the conversation so far: {session_summary}\n\n"
            + system_prompt
        )
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

    # 6b. Every Nth turn (or on explicit recap), refresh the session summary in
    # Redis and persist it as an episodic memory for cross-session continuity.
    turns = await redis_client.incr(f"{session_key}:turns")
    await redis_client.expire(f"{session_key}:turns", SESSION_TTL_SECONDS)
    if _wants_recap(user_message) or turns % SUMMARY_EVERY_N_TURNS == 0:
        try:
            raw_latest = await redis_client.lrange(
                session_key, -SESSION_MAX_MESSAGES, -1
            )
            latest_history = [json.loads(item) for item in raw_latest]
            summary = await _generate_session_summary(
                latest_history, session_key, redis_client
            )
            await _store_summary_memory(summary, user_id, session_id, db_session)
        except Exception:  # noqa: BLE001 - summary is best-effort
            logger.exception("Session summary generation failed")

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
