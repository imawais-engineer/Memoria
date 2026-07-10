"""Memory management API for the admin/dashboard frontend.

Exposes read + delete operations under the ``/api`` prefix. Destructive
operations are guarded by a fixed demo token (``X-API-Token`` header).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.database import get_db
from app.memory.models import Memory

router = APIRouter(prefix="/api", tags=["memories"])


class MemoryOut(BaseModel):
    """Memory representation for the frontend (embeddings excluded)."""

    id: str
    type: str
    content: str
    importance: float
    created_at: datetime | None
    decay_rate: float


def require_token(x_api_token: str = Header(default="")) -> None:
    """Simple fixed-token auth for destructive endpoints (demo only)."""

    if x_api_token != get_settings().demo_api_token:
        raise HTTPException(status_code=401, detail="Invalid or missing API token")


@router.get("/memories", response_model=list[MemoryOut])
async def list_memories(
    user_id: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
) -> list[MemoryOut]:
    """Return a user's active (non-archived) memories, newest first."""

    stmt = (
        select(Memory)
        .where(Memory.user_id == user_id, Memory.archived.is_(False))
        .order_by(Memory.created_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        MemoryOut(
            id=str(m.id),
            type=m.type,
            content=m.content,
            importance=m.importance,
            created_at=m.created_at,
            decay_rate=m.decay_rate,
        )
        for m in rows
    ]


@router.delete("/memories/{memory_id}")
async def delete_memory(
    memory_id: str,
    user_id: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_token),
) -> dict:
    """Delete a memory if it belongs to ``user_id``."""

    try:
        mem_uuid = uuid.UUID(memory_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid memory id")

    result = await db.execute(
        delete(Memory).where(Memory.id == mem_uuid, Memory.user_id == user_id)
    )
    await db.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"deleted": memory_id}
