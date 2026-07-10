"""Chat API: POST /chat."""

from __future__ import annotations

import redis.asyncio as redis
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis_client import get_redis
from app.services.agent_service import handle_message

router = APIRouter()


class ChatRequest(BaseModel):
    user_id: str
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str


@router.post("/chat", response_model=ChatResponse, tags=["chat"])
async def chat(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
) -> ChatResponse:
    """Process one chat turn: retrieve memory, call Qwen, persist session."""

    result = await handle_message(
        body.user_id,
        body.message,
        body.session_id,
        db_session=db,
        redis_client=redis_client,
    )
    return ChatResponse(**result)
