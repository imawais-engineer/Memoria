"""Authentication API: signup and login with username + favorite book."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    username: str = Field(..., min_length=1)
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)
    favorite_book: str = Field(..., min_length=1)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    favorite_book: str = Field(..., min_length=1)


class AuthResponse(BaseModel):
    user_id: str
    username: str
    global_memory_enabled: bool = True


class PreferencesRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    global_memory_enabled: bool


class UserPreferencesOut(BaseModel):
    user_id: str
    username: str
    global_memory_enabled: bool


async def _get_user_or_404(user_id: str, db: AsyncSession) -> User:
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user id")

    user = await db.get(User, user_uuid)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _user_to_auth(user: User) -> AuthResponse:
    return AuthResponse(
        user_id=str(user.id),
        username=user.username,
        global_memory_enabled=user.global_memory_enabled,
    )


def _user_to_preferences(user: User) -> UserPreferencesOut:
    return UserPreferencesOut(
        user_id=str(user.id),
        username=user.username,
        global_memory_enabled=user.global_memory_enabled,
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
    """Return the user's Personal Intelligence preference."""

    user = await _get_user_or_404(user_id, db)
    return _user_to_preferences(user)


@router.patch("/preferences", response_model=UserPreferencesOut)
async def update_preferences(
    body: PreferencesRequest,
    db: AsyncSession = Depends(get_db),
) -> UserPreferencesOut:
    """Update whether the agent may access memories across all chats."""

    user = await _get_user_or_404(body.user_id, db)
    user.global_memory_enabled = body.global_memory_enabled
    await db.commit()
    await db.refresh(user)
    return _user_to_preferences(user)
