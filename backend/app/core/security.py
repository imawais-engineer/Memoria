"""Security helpers: soft-password hashing and the shared demo-token guard."""

from __future__ import annotations

import hashlib
import hmac
import secrets

from fastapi import Header, HTTPException

from app.config import get_settings

_PREFIX = "scrypt"
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_DKLEN = 32


def _normalize(secret: str) -> bytes:
    return secret.strip().casefold().encode("utf-8")


def _derive(secret: str, salt: bytes) -> bytes:
    return hashlib.scrypt(
        _normalize(secret), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P,
        dklen=_DKLEN,
    )


def is_hashed(stored: str) -> bool:
    """Return True if ``stored`` is in the ``scrypt$salt$hash`` format."""

    return stored.startswith(f"{_PREFIX}$")


def hash_secret(secret: str) -> str:
    """Hash a secret (case/whitespace-insensitive) as ``scrypt$<salt>$<hash>``."""

    salt = secrets.token_bytes(16)
    return f"{_PREFIX}${salt.hex()}${_derive(secret, salt).hex()}"


def verify_secret(secret: str, stored: str) -> bool:
    """Verify ``secret`` against a hash, or a legacy plaintext value."""

    if not is_hashed(stored):
        return hmac.compare_digest(secret.encode("utf-8"), stored.encode("utf-8"))
    try:
        _, salt_hex, hash_hex = stored.split("$", 2)
        expected = bytes.fromhex(hash_hex)
        actual = _derive(secret, bytes.fromhex(salt_hex))
    except ValueError:
        return False
    return hmac.compare_digest(actual, expected)


def require_token(x_api_token: str = Header(default="")) -> None:
    """Fixed-token auth for destructive endpoints (demo only)."""

    expected = get_settings().demo_api_token
    if not hmac.compare_digest(
        x_api_token.encode("utf-8"), str(expected).encode("utf-8")
    ):
        raise HTTPException(status_code=401, detail="Invalid or missing API token")
