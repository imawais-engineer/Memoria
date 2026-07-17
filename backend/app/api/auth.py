"""Authentication API: signup and login with username + favorite book."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.persona import normalize_persona

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    username: str = Field(..., min_length=1)
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)
    favorite_book: str = Field(..., min_length=1)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    favorite_book: str = Field(..., min_length=1)


class PersonaIn(BaseModel):
    response_length: Literal["concise", "balanced", "detailed"] = "balanced"
    tone: Literal["professional", "friendly", "educational", "witty", "custom"] = (
        "professional"
    )
    behavior: Literal["cautious", "encouraging", "direct", "custom"] = "cautious"
    custom_tone: str | None = None
    custom_behavior: str | None = None

    @model_validator(mode="after")
    def validate_custom_fields(self) -> "PersonaIn":
        if self.tone == "custom" and not (self.custom_tone or "").strip():
            raise ValueError("custom_tone is required when tone is custom")
        if self.behavior == "custom" and not (self.custom_behavior or "").strip():
            raise ValueError("custom_behavior is required when behavior is custom")
        return self


class PersonaOut(BaseModel):
    response_length: Literal["concise", "balanced", "detailed"]
    tone: Literal["professional", "friendly", "educational", "witty", "custom"]
    behavior: Literal["cautious", "encouraging", "direct", "custom"]
    custom_tone: str | None = None
    custom_behavior: str | None = None


class AuthResponse(BaseModel):
    user_id: str
    username: str
    first_name: str = ""
    last_name: str = ""
    global_memory_enabled: bool = True
    persona: PersonaOut


class PreferencesRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    global_memory_enabled: bool | None = None
    persona: PersonaIn | None = None

    @model_validator(mode="after")
    def validate_update_fields(self) -> "PreferencesRequest":
        if self.global_memory_enabled is None and self.persona is None:
            raise ValueError(
                "At least one of global_memory_enabled or persona must be provided"
            )
        return self


class UserPreferencesOut(BaseModel):
    user_id: str
    username: str
    global_memory_enabled: bool
    persona: PersonaOut


async def _get_user_or_404(user_id: str, db: AsyncSession) -> User:
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user id")

    user = await db.get(User, user_uuid)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _persona_out(persona: dict | None) -> PersonaOut:
    normalized = normalize_persona(persona)
    return PersonaOut(**normalized)


def _user_to_auth(user: User) -> AuthResponse:
    return AuthResponse(
        user_id=str(user.id),
        username=user.username,
        first_name=user.first_name or "",
        last_name=user.last_name or "",
        global_memory_enabled=user.global_memory_enabled,
        persona=_persona_out(user.persona),
    )


def _user_to_preferences(user: User) -> UserPreferencesOut:
    return UserPreferencesOut(
        user_id=str(user.id),
        username=user.username,
        global_memory_enabled=user.global_memory_enabled,
        persona=_persona_out(user.persona),
    )


@router.post("/signup", response_model=AuthResponse)
async def signup(
    body: SignupRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Register a new user. Returns 409 if the username is taken."""

    existing = (
        await db.execute(select(User).where(User.username == body.username))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Username already exists")

    user = User(
        username=body.username,
        first_name=body.first_name,
        last_name=body.last_name,
        favorite_book=body.favorite_book,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Username already exists")
    await db.refresh(user)

    return _user_to_auth(user)


@router.post("/login", response_model=AuthResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Authenticate with username and favorite book. Returns 401 on mismatch."""

    user = (
        await db.execute(select(User).where(User.username == body.username))
    ).scalar_one_or_none()
    if user is None or user.favorite_book != body.favorite_book:
        raise HTTPException(status_code=401, detail="Invalid username or favorite book")

    return _user_to_auth(user)


@router.get("/preferences", response_model=UserPreferencesOut)
async def get_preferences(
    user_id: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
) -> UserPreferencesOut:
    """Return the user's preferences, including persona settings."""

    user = await _get_user_or_404(user_id, db)
    return _user_to_preferences(user)


@router.patch("/preferences", response_model=UserPreferencesOut)
async def update_preferences(
    body: PreferencesRequest,
    db: AsyncSession = Depends(get_db),
) -> UserPreferencesOut:
    """Update Personal Intelligence and/or persona settings."""

    user = await _get_user_or_404(body.user_id, db)
    if body.global_memory_enabled is not None:
        user.global_memory_enabled = body.global_memory_enabled
    if body.persona is not None:
        user.persona = body.persona.model_dump()
    await db.commit()
    await db.refresh(user)
    return _user_to_preferences(user)
