"""Core chat agent orchestration.

``handle_message`` ties together short-term session memory (Redis), long-term
memory retrieval (pgvector), the Qwen chat model, and background memory
ingestion (Celery).
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

from collections.abc import AsyncIterator

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dashscope_client import (
    ALLOWED_CHAT_MODELS,
    DEFAULT_CHAT_MODEL,
    call_qwen_chat,
    get_embedding,
    stream_qwen_chat,
)
from app.memory.models import Memory
from app.models.chat_message import ChatMessage
from app.models.user import User
from app.api.sessions import ensure_session_exists, touch_session_on_message
from app.services.memoria_knowledge import MEMORIA_KNOWLEDGE_BASE
from app.services.session_titles import SLASH_HELP_REPLY
from app.memory.reflection import generate_user_reflection, get_latest_reflection
from app.memory.retrieval import retrieve_context_and_ids
from app.schemas.persona import format_persona_prompt

logger = logging.getLogger(__name__)

# Chat model (per roadmap Module 6).
CHAT_MODEL = "qwen-plus"

# Keep only the most recent N messages of session history in Redis.
SESSION_MAX_MESSAGES = 10

# Session state expires after this many seconds of inactivity (7 days).
SESSION_TTL_SECONDS = 7 * 24 * 60 * 60

# Regenerate the rolling session summary every N turns (or on explicit recap).
SUMMARY_EVERY_N_TURNS = 5

# Trigger reflective memory synthesis every N user messages in a session.
REFLECTION_EVERY_N_USER_MESSAGES = 10

# Importance/decay for a persisted session-summary memory.
SESSION_SUMMARY_IMPORTANCE = 0.7
SESSION_SUMMARY_DECAY_RATE = 0.02

# Substrings that trigger an on-demand recap/summary.
RECAP_KEYWORDS = ("recap", "summar", "remind me")

SYSTEM_PROMPT_TEMPLATE = (
    "You are a personal AI with memory. Here is what you know about the user: "
    "{memory_context}. Use this to personalise responses. "
    "Format your answers clearly. Use empty lines between paragraphs, "
    "proper Markdown headings when helpful, and tables where appropriate."
)

MEMORIA_CAPABILITIES = (
    "You are an AI assistant inside Memoria – a self‑evolving personal memory agent.\n"
    "Memoria stores user‑centric facts (preferences, goals, identity) across sessions.\n"
    "It supports slash commands typed by the user:\n"
    "/imagine <prompt>        – generate an image\n"
    "/gen_video <prompt>      – generate a video\n"
    "/gen_voice <prompt>      – generate a voice overview\n"
    "/memorize <fact>         – manually store a memory\n"
    "/create_task <title>     – create a task\n"
    "/tasks_list              – list pending tasks\n"
    "/task_complete <id>      – mark a task as complete\n"
    "/list_memory             – list memories (scoped by Personal Intelligence)\n"
    "/forget_memory <id|ALL>  – forget one or all memories\n"
    "When a user sends a slash command without required parameters (e.g., just\n"
    "'/task_complete'), respond with a helpful reminder of the correct syntax,\n"
    "don't treat it as a normal conversation."
)

MEMORIA_IDENTITY = (
    "When a user asks who you are or about your identity, respond with something like:\n"
    "'I am **Memoria** – powered by the most powerful Qwen Models from Alibaba Cloud,\n"
    "designed especially for personal memory management. I am a Self‑Evolving Personal AI\n"
    "with Human‑like Memory.'\n"
    "Always mention that you run on Qwen Cloud and use the bold style for the word\n"
    "'Memoria' to make it stand out."
)


def _memory_mode_label(is_memoryless: bool, global_memory_enabled: bool) -> str:
    """Return the Personal Intelligence / MemoryLess status line for the prompt."""

    if is_memoryless:
        return "[MemoryLess Session – no personal memories are available.]"
    if global_memory_enabled:
        return (
            "[Personal Intelligence is ON. You have full access to the "
            "user's life memories.]"
        )
    return (
        "[Personal Intelligence is OFF. You are using only this session's "
        "conversation memory and manually saved core facts.]"
    )


async def _archive_chat_messages(
    session_id: str,
    user_message: str,
    reply: str,
    db_session: AsyncSession,
) -> None:
    """Persist a full exchange to the Context Archive for deep recall."""

    session_uuid = uuid.UUID(session_id)
    db_session.add(
        ChatMessage(session_id=session_uuid, role="user", content=user_message)
    )
    db_session.add(
        ChatMessage(session_id=session_uuid, role="assistant", content=reply)
    )
    await db_session.commit()


def _wants_recap(message: str) -> bool:
    """Return True if the user is explicitly asking for a recap/summary."""

    lowered = message.lower()
    return any(keyword in lowered for keyword in RECAP_KEYWORDS)


async def _get_global_memory_enabled(user_id: str, db_session: AsyncSession) -> bool:
    """Return whether cross-chat memory access is enabled for a registered user."""

    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        return True

    user = await db_session.get(User, user_uuid)
    if user is None:
        return True
    return user.global_memory_enabled


async def _get_user_persona(user_id: str, db_session: AsyncSession) -> dict | None:
    """Return the stored persona for a registered user, if any."""

    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        return None

    user = await db_session.get(User, user_uuid)
    if user is None:
        return None
    return user.persona


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
    session_uuid = uuid.UUID(session_id)
    db_session.add(
        Memory(
            user_id=user_id,
            type="episodic",
            content=summary,
            embedding=embedding,
            importance=SESSION_SUMMARY_IMPORTANCE,
            decay_rate=SESSION_SUMMARY_DECAY_RATE,
            session_id=session_uuid,
            meta_data={"kind": "session_summary", "session_id": session_id},
        )
    )
    await db_session.commit()


async def _run_reflection_background(user_id: str) -> None:
    """Generate a user reflection without blocking the chat response."""

    from app.core.database import async_session

    try:
        async with async_session() as session:
            reflection = await generate_user_reflection(user_id, session)
            if reflection:
                logger.info(
                    "Background reflection stored for user_id=%s: %s",
                    user_id,
                    reflection[:120],
                )
    except Exception:  # noqa: BLE001 - reflection is best-effort
        logger.exception("Background reflection failed for user_id=%s", user_id)


async def _prepare_chat_turn(
    user_id: str,
    user_message: str,
    session_id: str | None,
    *,
    is_memoryless: bool,
    db_session: AsyncSession,
    redis_client: redis.Redis,
) -> dict:
    """Build chat context for a turn. May include an early ``reply`` for slash help."""

    if not session_id:
        session_id = str(uuid.uuid4())

    session = await ensure_session_exists(
        session_id,
        user_id,
        is_memoryless=is_memoryless,
        db=db_session,
    )
    is_memoryless = session.is_memoryless

    if user_message.strip() == "/":
        await touch_session_on_message(session_id, user_message, db_session)
        return {
            "early_reply": SLASH_HELP_REPLY,
            "session_id": session_id,
            "memory_ids": [],
            "title": session.title if session.title != "New Chat" else None,
        }

    session_title = await touch_session_on_message(session_id, user_message, db_session)
    global_memory_enabled = await _get_global_memory_enabled(user_id, db_session)
    user_persona = await _get_user_persona(user_id, db_session)
    session_key = f"session:{session_id}"

    raw_history = await redis_client.lrange(session_key, -SESSION_MAX_MESSAGES, -1)
    history: list[dict] = []
    for item in raw_history:
        try:
            history.append(json.loads(item))
        except (json.JSONDecodeError, TypeError):
            continue

    memory_context, memory_ids = await retrieve_context_and_ids(
        user_id,
        user_message,
        max_tokens=6000,
        db_session=db_session,
        session_id=session_id,
        is_memoryless=is_memoryless,
        global_memory_enabled=global_memory_enabled,
    )
    reflection_text = None
    if not is_memoryless and global_memory_enabled:
        reflection_text = await get_latest_reflection(user_id, db_session)

    session_summary = await redis_client.get(f"{session_key}:summary")
    memory_display = memory_context or "(none)"
    system_prompt = (
        f"{_memory_mode_label(is_memoryless, global_memory_enabled)}\n\n"
        + SYSTEM_PROMPT_TEMPLATE.format(memory_context=memory_display)
    )
    if reflection_text:
        system_prompt += f"\n\nLatest reflection about the user: {reflection_text}"
    system_prompt += f"\n\n{format_persona_prompt(user_persona)}"
    system_prompt += f"\n\n{MEMORIA_CAPABILITIES}"
    system_prompt += f"\n\n{MEMORIA_IDENTITY}"
    system_prompt += (
        "\n\n---\nWhen users ask how Memoria works, its architecture, features, "
        "structure, or implementation, use this knowledge base:\n\n"
        f"{MEMORIA_KNOWLEDGE_BASE}"
    )
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

    return {
        "session_id": session_id,
        "session_key": session_key,
        "session_title": session_title,
        "is_memoryless": is_memoryless,
        "memory_ids": memory_ids,
        "messages": messages,
        "user_message": user_message,
        "user_id": user_id,
    }


async def _finalize_chat_turn(
    *,
    user_id: str,
    user_message: str,
    reply: str,
    session_id: str,
    session_key: str,
    is_memoryless: bool,
    db_session: AsyncSession,
    redis_client: redis.Redis,
) -> None:
    """Persist chat side effects after the assistant reply is complete."""

    if not is_memoryless:
        try:
            await _archive_chat_messages(session_id, user_message, reply, db_session)
        except Exception:  # noqa: BLE001 - archive must not break chat
            logger.exception(
                "Failed to archive chat messages for session_id=%s", session_id
            )

    await redis_client.rpush(
        session_key,
        json.dumps({"role": "user", "content": user_message}),
        json.dumps({"role": "assistant", "content": reply}),
    )
    await redis_client.ltrim(session_key, -SESSION_MAX_MESSAGES, -1)
    await redis_client.expire(session_key, SESSION_TTL_SECONDS)

    turns = await redis_client.incr(f"{session_key}:turns")
    await redis_client.expire(f"{session_key}:turns", SESSION_TTL_SECONDS)
    if not is_memoryless and (
        _wants_recap(user_message) or turns % SUMMARY_EVERY_N_TURNS == 0
    ):
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

    if not is_memoryless:
        message_id = str(uuid.uuid4())
        try:
            from celery_app.tasks import extract_memories_task

            extract_memories_task.delay(
                conversation_text=user_message,
                user_id=user_id,
                message_id=message_id,
                session_id=session_id,
                is_memoryless=False,
            )
        except Exception:  # noqa: BLE001 - enqueue failure must not break the reply
            logger.exception(
                "Failed to enqueue extract_memories_task for session_id=%s",
                session_id,
            )
    else:
        logger.info(
            "Skipping memory extraction enqueue for memoryless session_id=%s",
            session_id,
        )

    user_msg_count = await redis_client.incr(f"{session_key}:user_msg_count")
    await redis_client.expire(f"{session_key}:user_msg_count", SESSION_TTL_SECONDS)
    if not is_memoryless and user_msg_count % REFLECTION_EVERY_N_USER_MESSAGES == 0:
        asyncio.create_task(_run_reflection_background(user_id))


async def handle_message_stream(
    user_id: str,
    user_message: str,
    session_id: str | None = None,
    *,
    is_memoryless: bool = False,
    model: str = DEFAULT_CHAT_MODEL,
    db_session: AsyncSession,
    redis_client: redis.Redis,
) -> AsyncIterator[dict]:
    """Stream chat tokens, then yield a final done event."""

    if model not in ALLOWED_CHAT_MODELS:
        model = DEFAULT_CHAT_MODEL

    prepared = await _prepare_chat_turn(
        user_id,
        user_message,
        session_id,
        is_memoryless=is_memoryless,
        db_session=db_session,
        redis_client=redis_client,
    )

    if "early_reply" in prepared:
        yield {"type": "token", "token": prepared["early_reply"]}
        yield {
            "type": "done",
            "session_id": prepared["session_id"],
            "memory_ids": prepared["memory_ids"],
            "title": prepared.get("title"),
        }
        return

    reply_parts: list[str] = []
    async for token in stream_qwen_chat(prepared["messages"], model=model):
        reply_parts.append(token)
        yield {"type": "token", "token": token}

    reply = "".join(reply_parts)
    await _finalize_chat_turn(
        user_id=prepared["user_id"],
        user_message=prepared["user_message"],
        reply=reply,
        session_id=prepared["session_id"],
        session_key=prepared["session_key"],
        is_memoryless=prepared["is_memoryless"],
        db_session=db_session,
        redis_client=redis_client,
    )

    yield {
        "type": "done",
        "session_id": prepared["session_id"],
        "memory_ids": prepared["memory_ids"],
        "title": prepared["session_title"],
    }


async def handle_message(
    user_id: str,
    user_message: str,
    session_id: str | None = None,
    *,
    is_memoryless: bool = False,
    model: str = DEFAULT_CHAT_MODEL,
    db_session: AsyncSession,
    redis_client: redis.Redis,
) -> dict:
    """Handle one chat turn and return ``{"reply": ..., "session_id": ...}``.

    ``db_session`` and ``redis_client`` are injected (from FastAPI dependencies).
    """

    if model not in ALLOWED_CHAT_MODELS:
        model = DEFAULT_CHAT_MODEL

    prepared = await _prepare_chat_turn(
        user_id,
        user_message,
        session_id,
        is_memoryless=is_memoryless,
        db_session=db_session,
        redis_client=redis_client,
    )

    if "early_reply" in prepared:
        return {
            "reply": prepared["early_reply"],
            "session_id": prepared["session_id"],
            "memory_ids": prepared["memory_ids"],
            "title": prepared.get("title"),
        }

    reply = await call_qwen_chat(prepared["messages"], model=model)
    await _finalize_chat_turn(
        user_id=prepared["user_id"],
        user_message=prepared["user_message"],
        reply=reply,
        session_id=prepared["session_id"],
        session_key=prepared["session_key"],
        is_memoryless=prepared["is_memoryless"],
        db_session=db_session,
        redis_client=redis_client,
    )

    return {
        "reply": reply,
        "session_id": prepared["session_id"],
        "memory_ids": prepared["memory_ids"],
        "title": prepared["session_title"],
    }
