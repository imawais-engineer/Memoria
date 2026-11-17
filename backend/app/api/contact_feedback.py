"""User contact feedback API (distinct from memory rating feedback)."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import authorize_claimed_user, get_optional_user
from app.core.database import get_db
from app.models.contact_feedback import ContactFeedback

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["contact-feedback"])


class ContactFeedbackRequest(BaseModel):
    user_id: str | None = None
    name: str = Field(..., min_length=1)
    email: str = Field(..., min_length=3)
    feedback: str = Field(..., min_length=1)


class ContactFeedbackResponse(BaseModel):
    success: bool = True


@router.post("/contact-feedback", response_model=ContactFeedbackResponse)
async def submit_contact_feedback(
    body: ContactFeedbackRequest,
    current_user: str | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> ContactFeedbackResponse:
    """Store user feedback and log it for review."""

    user_uuid = None
    if current_user:
        authorize_claimed_user(body.user_id, current_user)
        try:
            user_uuid = uuid.UUID(current_user)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user id")

    entry = ContactFeedback(
        user_id=user_uuid,
        name=body.name.strip(),
        email=body.email,
        message=body.feedback.strip(),
    )
    db.add(entry)
    await db.commit()

    logger.info(
        "Contact feedback from %s <%s>: %s",
        entry.name,
        entry.email,
        entry.message[:200],
    )

    return ContactFeedbackResponse()
