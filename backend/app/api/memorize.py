"""Manual memory creation API."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dashscope_client import get_embedding
from app.core.database import get_db
from app.memory.models import Memory
from app.models.user import User

router = APIRouter(prefix="/api", tags=["memorize"])


class MemorizeRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)


class MemorizeResponse(BaseModel):
    id: str
    success: bool = True


@router.post("/memorize", response_model=MemorizeResponse)
async def memorize(
    body: MemorizeRequest,
    db: AsyncSession = Depends(get_db),
) -> MemorizeResponse:
    """Create a core memory directly without LLM processing."""

    try:
        user_uuid = uuid.UUID(body.user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user id")

    user = await db.get(User, user_uuid)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    content = body.content.strip()
    embedding = await get_embedding(content)
    memory = Memory(
        user_id=body.user_id,
        type="core",
        content=content,
        embedding=embedding,
        importance=1.0,
    )
    db.add(memory)
    await db.commit()
    await db.refresh(memory)

    return MemorizeResponse(id=str(memory.id))
