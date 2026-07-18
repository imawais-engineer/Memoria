"""Memory management API for the admin/dashboard frontend.

Exposes read + delete operations under the ``/api`` prefix. Destructive
operations are guarded by a fixed demo token (``X-API-Token`` header).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
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
    session_id: str | None = None


class MemoryStatsOut(BaseModel):
    """Aggregate memory statistics for the dashboard."""

    total_memories: int
    consolidated_count: int
    summaries_count: int
    avg_importance: float
    last_consolidation: datetime | None
    types: dict[str, int] = Field(default_factory=dict)


def require_token(x_api_token: str = Header(default="")) -> None:
    """Simple fixed-token auth for destructive endpoints (demo only)."""

    if x_api_token != get_settings().demo_api_token:
        raise HTTPException(status_code=401, detail="Invalid or missing API token")


@router.get("/memory-stats", response_model=MemoryStatsOut)
async def memory_stats(
    user_id: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_token),
) -> MemoryStatsOut:
    """Return aggregate memory statistics for the dashboard."""

    active_filter = (Memory.user_id == user_id, Memory.archived.is_(False))

    total_memories = (
        await db.execute(select(func.count()).select_from(Memory).where(*active_filter))
    ).scalar_one()

    consolidated_count = (
        await db.execute(
            select(func.count())
            .select_from(Memory)
            .where(*active_filter, Memory.is_consolidated.is_(True))
        )
    ).scalar_one()

    summaries_count = (
        await db.execute(
            select(func.count())
            .select_from(Memory)
            .where(
                *active_filter,
                Memory.meta_data["source"].astext == "consolidation",
            )
        )
    ).scalar_one()

    avg_importance_raw = (
        await db.execute(
            select(func.avg(Memory.importance)).select_from(Memory).where(*active_filter)
        )
    ).scalar_one()
    avg_importance = float(avg_importance_raw or 0.0)

    last_consolidation = (
        await db.execute(
            select(func.max(Memory.consolidated_at))
            .select_from(Memory)
            .where(Memory.user_id == user_id, Memory.consolidated_at.is_not(None))
        )
    ).scalar_one()

    type_rows = (
        await db.execute(
            select(Memory.type, func.count())
            .select_from(Memory)
            .where(*active_filter)
            .group_by(Memory.type)
        )
    ).all()

    types = {str(memory_type): int(count) for memory_type, count in type_rows}

    return MemoryStatsOut(
        total_memories=total_memories,
        consolidated_count=consolidated_count,
        summaries_count=summaries_count,
        avg_importance=round(avg_importance, 2),
        last_consolidation=last_consolidation,
        types=types,
    )


@router.get("/memories", response_model=list[MemoryOut])
async def list_memories(
    user_id: str = Query(..., min_length=1),
    session_id: str | None = Query(None, min_length=1),
    db: AsyncSession = Depends(get_db),
) -> list[MemoryOut]:
    """Return a user's active (non-archived) memories.

    When ``session_id`` is provided, only memories for that session are returned,
    ordered oldest-first for stable chat command numbering.
  """

    filters = [Memory.user_id == user_id, Memory.archived.is_(False)]

    if session_id is not None:
        try:
            session_uuid = uuid.UUID(session_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid session id")
        filters.append(Memory.session_id == session_uuid)
        order_by = Memory.created_at.asc()
    else:
        order_by = Memory.created_at.desc()

    stmt = select(Memory).where(*filters).order_by(order_by)
    rows = (await db.execute(stmt)).scalars().all()
    return [
        MemoryOut(
            id=str(m.id),
            type=m.type,
            content=m.content,
            importance=m.importance,
            created_at=m.created_at,
            decay_rate=m.decay_rate,
            session_id=str(m.session_id) if m.session_id else None,
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
