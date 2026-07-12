"""Authentication API: signup and login with username + favorite book."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
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

    return AuthResponse(user_id=str(user.id), username=user.username)


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

    return AuthResponse(user_id=str(user.id), username=user.username)
