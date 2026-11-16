"""Manual memory creation API."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dashscope_client import get_embedding
from app.core.auth import authorize_claimed_user, get_current_user
from app.core.database import get_db
from app.services.limits import enforce_limits
from app.memory.models import Memory
from app.models.user import User

router = APIRouter(prefix="/api", tags=["memorize"])


class MemorizeRequest(BaseModel):
    user_id: str | None = None
    content: str = Field(..., min_length=1)


class MemorizeResponse(BaseModel):
    id: str
    success: bool = True


@router.post("/memorize", response_model=MemorizeResponse)
async def memorize(
    body: MemorizeRequest,
    current_user: str = Depends(enforce_limits),
    db: AsyncSession = Depends(get_db),
) -> MemorizeResponse:
    """Create a core memory directly without LLM processing."""

    user_id = authorize_claimed_user(body.user_id, current_user)
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user id")

    user = await db.get(User, user_uuid)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    content = body.content.strip()
    embedding = await get_embedding(content)
    memory = Memory(
        user_id=user_id,
        type="core",
        content=content,
        embedding=embedding,
        importance=1.0,
    )
    db.add(memory)
    await db.commit()
    await db.refresh(memory)

    return MemorizeResponse(id=str(memory.id))
