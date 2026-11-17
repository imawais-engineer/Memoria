"""JWT access tokens and the ``get_current_user`` dependency.

Tokens are HS256 signed with ``SECRET_KEY``. The subject (``sub``) is the user
UUID. Routes take the caller identity from the token only; a ``user_id`` sent
by the client is accepted for backward compatibility but must match.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, Header, HTTPException

from app.config import Settings, get_settings

ALGORITHM = "HS256"
ISSUER = "memoria"


def create_access_token(
    user_id: str, settings: Settings | None = None, *, ttl_minutes: int | None = None
) -> str:
    settings = settings or get_settings()
    now = datetime.now(timezone.utc)
    ttl = settings.access_token_ttl_minutes if ttl_minutes is None else ttl_minutes
    payload = {
        "sub": str(user_id),
        "iss": ISSUER,
        "iat": now,
        "exp": now + timedelta(minutes=ttl),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str, settings: Settings | None = None) -> str:
    """Return the user id for a valid token or raise ``HTTPException(401)``."""

    settings = settings or get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[ALGORITHM],
            issuer=ISSUER,
            options={"require": ["exp", "sub", "iss"]},
        )
        return str(uuid.UUID(str(payload["sub"])))
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(authorization: str = Header(default="")) -> str:
    """FastAPI dependency: the authenticated user id (UUID string)."""

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=401,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_access_token(token.strip())


CurrentUser = Depends(get_current_user)


def authorize_claimed_user(claimed: str | None, current_user: str) -> str:
    """Return the token's user id; 403 if the client claimed another user."""

    if claimed and claimed.strip().lower() != current_user.lower():
        raise HTTPException(status_code=403, detail="Forbidden: user mismatch")
    return current_user


def get_optional_user(authorization: str = Header(default="")) -> str | None:
    """Like ``get_current_user`` but returns None when no token is sent."""

    if not authorization.strip():
        return None
    return get_current_user(authorization)
