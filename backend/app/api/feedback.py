"""User feedback API for adjusting memory importance from chat ratings."""

from __future__ import annotations

import logging
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.memory.models import Memory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["feedback"])

IMPORTANCE_BOOST = 0.5
IMPORTANCE_CAP = 1.0
IMPORTANCE_FLOOR = 0.1


class FeedbackRequest(BaseModel):
    """Thumbs-up/down feedback tied to memories used in a chat reply."""

    user_id: str = Field(..., min_length=1)
    memory_ids: list[str] = Field(default_factory=list)
    rating: Literal["positive", "negative"]


class FeedbackResponse(BaseModel):
    """Result of applying feedback to one or more memories."""

    status: str
    updated: int


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    body: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
) -> FeedbackResponse:
    """Adjust memory importance based on user feedback on a chat response."""

    if not body.memory_ids:
        return FeedbackResponse(status="ok", updated=0)

    updated = 0
    for memory_id in body.memory_ids:
        try:
            mem_uuid = uuid.UUID(memory_id)
        except ValueError:
            logger.warning("Skipping invalid memory_id in feedback: %s", memory_id)
            continue

        memory = await db.get(Memory, mem_uuid)
        if memory is None or memory.user_id != body.user_id:
            continue

        if body.rating == "positive":
            memory.importance = min(IMPORTANCE_CAP, memory.importance + IMPORTANCE_BOOST)
        else:
            memory.importance = max(IMPORTANCE_FLOOR, memory.importance - IMPORTANCE_BOOST)
            if memory.importance <= IMPORTANCE_FLOOR:
                memory.archived = True

        updated += 1
        logger.info(
            "Feedback %s applied to memory_id=%s importance=%.2f archived=%s",
            body.rating,
            memory_id,
            memory.importance,
            memory.archived,
        )

    await db.commit()
    return FeedbackResponse(status="ok", updated=updated)
