"""Context Archive API for on-demand transcript search."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.memories import require_token
from app.core.database import get_db
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession

router = APIRouter(prefix="/api", tags=["archive"])


class ArchiveMessageOut(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    created_at: datetime | None


def _owner_filter(user_id: str):
    """SQLAlchemy filter for sessions owned by a registered user or guest."""

    try:
        registered_id = uuid.UUID(user_id)
        return ChatSession.user_id == registered_id
    except ValueError:
        return ChatSession.guest_user_id == user_id


@router.get("/search-archive", response_model=list[ArchiveMessageOut])
async def search_archive(
    user_id: str = Query(..., min_length=1),
    query: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_token),
) -> list[ArchiveMessageOut]:

    stmt = (
        select(ChatMessage)
        .join(ChatSession, ChatMessage.session_id == ChatSession.id)
        .where(_owner_filter(user_id))
        .where(ChatSession.is_memoryless.is_(False))
        .where(ChatMessage.content.ilike(f"%{query}%"))
        .order_by(ChatMessage.created_at.desc())
        .limit(20)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        ArchiveMessageOut(
            id=str(message.id),
            session_id=str(message.session_id),
            role=message.role,
            content=message.content,
            created_at=message.created_at,
        )
        for message in rows
    ]
