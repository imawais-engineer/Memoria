"""Chat API: POST /chat and POST /chat/stream."""

from __future__ import annotations

import json

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import authorize_claimed_user
from app.core.database import get_db
from app.core.redis_client import get_redis
from app.services.agent_service import handle_message, handle_message_stream
from app.services.limits import Limiter, enforce_limits, estimate_tokens, get_limiter
from app.services.usage import USAGE_LIMIT_MESSAGE, check_and_increment_usage

router = APIRouter()


class ChatRequest(BaseModel):
    user_id: str | None = None
    message: str
    session_id: str | None = None
    is_memoryless: bool = False
    model: str = "qwen-plus"


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    memory_ids: list[str] = []
    title: str | None = None


async def _enforce_message_limit(db: AsyncSession, user_id: str) -> None:
    """Raise 429 when the user has exhausted their message quota."""

    allowed = await check_and_increment_usage(db, user_id, "message")
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=USAGE_LIMIT_MESSAGE,
        )


@router.post("/chat", response_model=ChatResponse, tags=["chat"])
async def chat(
    body: ChatRequest,
    current_user: str = Depends(enforce_limits),
    limiter: Limiter = Depends(get_limiter),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
) -> ChatResponse:
    """Process one chat turn: retrieve memory, call the LLM, persist session."""

    user_id = authorize_claimed_user(body.user_id, current_user)
    await _enforce_message_limit(db, user_id)

    result = await handle_message(
        user_id,
        body.message,
        body.session_id,
        is_memoryless=body.is_memoryless,
        model=body.model,
        db_session=db,
        redis_client=redis_client,
    )
    await limiter.add_tokens(user_id, estimate_tokens(body.message, result.get("reply", "")))
    return ChatResponse(**result)


@router.post("/chat/stream", tags=["chat"])
async def chat_stream(
    body: ChatRequest,
    current_user: str = Depends(enforce_limits),
    limiter: Limiter = Depends(get_limiter),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
) -> StreamingResponse:
    """Stream one chat turn via Server-Sent Events."""

    user_id = authorize_claimed_user(body.user_id, current_user)
    await _enforce_message_limit(db, user_id)

    async def event_generator():
        try:
            streamed = 0
            async for event in handle_message_stream(
                user_id,
                body.message,
                body.session_id,
                is_memoryless=body.is_memoryless,
                model=body.model,
                db_session=db,
                redis_client=redis_client,
            ):
                if event["type"] == "token":
                    streamed += len(event["token"])
                    payload = {"token": event["token"]}
                else:
                    payload = {
                        "done": True,
                        "session_id": event["session_id"],
                        "memory_ids": event["memory_ids"],
                    }
                    if event.get("title"):
                        payload["title"] = event["title"]
                yield f"data: {json.dumps(payload)}\n\n"
            await limiter.add_tokens(
                user_id, estimate_tokens(body.message) + streamed // 4
            )
        except Exception as exc:  # noqa: BLE001
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
