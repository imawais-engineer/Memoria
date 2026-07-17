"""Chat session management API."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis_client import get_redis
from app.memory.models import Memory
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession  # noqa: F401  (register FK table)
from app.services.session_titles import SLASH_HELP_REPLY, generate_session_title, title_from_slash_message

router = APIRouter(tags=["sessions"])

SESSION_TTL_SECONDS = 7 * 24 * 60 * 60
DEFAULT_TITLE = "New Chat"
MAX_TITLE_LENGTH = 80


class CreateSessionRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    is_memoryless: bool = False


class SessionOut(BaseModel):
    session_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    is_memoryless: bool


class UpdateSessionRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=MAX_TITLE_LENGTH)


class DeleteSessionResponse(BaseModel):
    deleted_session_id: str
    deleted_memories: int


class ChatMessageOut(BaseModel):
    role: str
    content: str


def _parse_owner(user_id: str) -> tuple[uuid.UUID | None, str | None]:
    """Return ``(registered_user_uuid, guest_user_id)`` for an owner key."""

    try:
        return uuid.UUID(user_id), None
    except ValueError:
        return None, user_id


def _owner_filter(user_id: str):
    """SQLAlchemy filter for sessions owned by a user or guest."""

    registered_id, guest_id = _parse_owner(user_id)
    if registered_id is not None:
        return ChatSession.user_id == registered_id
    return ChatSession.guest_user_id == guest_id


def _session_to_out(session: ChatSession) -> SessionOut:
    return SessionOut(
        session_id=str(session.id),
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        is_memoryless=session.is_memoryless,
    )


def _title_from_message(message: str) -> str:
    cleaned = " ".join(message.strip().split())
    if not cleaned:
        return DEFAULT_TITLE
    if len(cleaned) <= MAX_TITLE_LENGTH:
        return cleaned
    return cleaned[: MAX_TITLE_LENGTH - 1].rstrip() + "…"


async def _get_owned_session(
    session_id: str,
    user_id: str,
    db: AsyncSession,
) -> ChatSession:
    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session id")

    session = (
        await db.execute(
            select(ChatSession).where(
                ChatSession.id == session_uuid,
                _owner_filter(user_id),
            )
        )
    ).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def _session_has_messages_filter():
    """Sessions that have at least one archived message or a non-default title."""

    return or_(
        ChatSession.title != DEFAULT_TITLE,
        exists().where(ChatMessage.session_id == ChatSession.id),
    )


async def ensure_session_exists(
    session_id: str,
    user_id: str,
    *,
    is_memoryless: bool = False,
    db: AsyncSession,
) -> ChatSession:
    """Create a chat session on first message when the id is not yet persisted."""

    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session id")

    existing = await db.get(ChatSession, session_uuid)
    if existing is not None:
        registered_id, guest_id = _parse_owner(user_id)
        owned = (
            existing.user_id == registered_id
            if registered_id is not None
            else existing.guest_user_id == guest_id
        )
        if not owned:
            raise HTTPException(status_code=404, detail="Session not found")
        return existing

    registered_id, guest_id = _parse_owner(user_id)
    session = ChatSession(
        id=session_uuid,
        user_id=registered_id,
        guest_user_id=guest_id,
        title=DEFAULT_TITLE,
        is_memoryless=is_memoryless,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def touch_session_on_message(
    session_id: str,
    user_message: str,
    db: AsyncSession,
) -> str | None:
    """Auto-title new chats and bump ``updated_at`` on activity.

    Returns the session title when set or already meaningful, else ``None``.
    """

    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError:
        return None

    session = (
        await db.execute(select(ChatSession).where(ChatSession.id == session_uuid))
    ).scalar_one_or_none()
    if session is None:
        return None

    values: dict = {"updated_at": datetime.now(timezone.utc)}
    new_title: str | None = None
    stripped = user_message.strip()
    if session.title == DEFAULT_TITLE and stripped and stripped != "/":
        new_title = await generate_session_title(user_message)
        values["title"] = new_title

    await db.execute(
        update(ChatSession).where(ChatSession.id == session_uuid).values(**values)
    )
    await db.commit()

    if new_title is not None:
        return new_title
    return session.title if session.title != DEFAULT_TITLE else None


@router.post("/sessions", response_model=SessionOut)
async def create_session(
    body: CreateSessionRequest,
    db: AsyncSession = Depends(get_db),
) -> SessionOut:
    """Create a new chat session for a registered user or guest."""

    registered_id, guest_id = _parse_owner(body.user_id)
    session = ChatSession(
        user_id=registered_id,
        guest_user_id=guest_id,
        title=DEFAULT_TITLE,
        is_memoryless=body.is_memoryless,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return _session_to_out(session)


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(
    user_id: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
) -> list[SessionOut]:
    """List sessions for a user, most recently updated first."""

    rows = (
        await db.execute(
            select(ChatSession)
            .where(_owner_filter(user_id), _session_has_messages_filter())
            .order_by(ChatSession.updated_at.desc())
        )
    ).scalars().all()
    return [_session_to_out(session) for session in rows]


@router.get("/sessions/{session_id}/history", response_model=list[ChatMessageOut])
async def get_session_history(
    session_id: str,
    user_id: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
) -> list[ChatMessageOut]:
    """Return short-term chat history for a session from Redis."""

    await _get_owned_session(session_id, user_id, db)

    session_key = f"session:{session_id}"
    raw_history = await redis_client.lrange(session_key, 0, -1)
    messages: list[ChatMessageOut] = []
    for item in raw_history:
        try:
            payload = json.loads(item)
            role = payload.get("role")
            content = payload.get("content")
            if role and content is not None:
                messages.append(ChatMessageOut(role=role, content=content))
        except (json.JSONDecodeError, TypeError):
            continue
    return messages


@router.patch("/sessions/{session_id}", response_model=SessionOut)
async def update_session(
    session_id: str,
    body: UpdateSessionRequest,
    user_id: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
) -> SessionOut:
    """Rename a chat session."""

    session = await _get_owned_session(session_id, user_id, db)
    session.title = body.title.strip()
    session.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(session)
    return _session_to_out(session)


@router.delete("/sessions/{session_id}", response_model=DeleteSessionResponse)
async def delete_session(
    session_id: str,
    user_id: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
) -> DeleteSessionResponse:
    """Delete a session and all memories extracted from that chat."""

    session = await _get_owned_session(session_id, user_id, db)

    memory_count = (
        await db.execute(
            select(func.count()).select_from(Memory).where(Memory.session_id == session.id)
        )
    ).scalar_one()
    deleted_memories = int(memory_count)

    await db.delete(session)
    await db.commit()

    session_key = f"session:{session_id}"
    await redis_client.delete(
        session_key,
        f"{session_key}:summary",
        f"{session_key}:turns",
        f"{session_key}:user_msg_count",
    )

    return DeleteSessionResponse(
        deleted_session_id=session_id,
        deleted_memories=deleted_memories,
    )
