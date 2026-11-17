"""Security helpers: soft-password hashing and the shared demo-token guard."""

from __future__ import annotations

import hashlib
import hmac
import secrets

from fastapi import Header, HTTPException

from app.config import demo_token_enabled, get_settings

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
        # Legacy plaintext: same normalization as hashed rows, so login
        # semantics do not change when a row is upgraded.
        return hmac.compare_digest(_normalize(secret), _normalize(stored))
    try:
        _, salt_hex, hash_hex = stored.split("$", 2)
        expected = bytes.fromhex(hash_hex)
        actual = _derive(secret, bytes.fromhex(salt_hex))
    except ValueError:
        return False
    return hmac.compare_digest(actual, expected)


# Verified against when the user does not exist, so unknown and known
# usernames cost the same scrypt derivation.
_DUMMY_HASH = hash_secret("dummy-secret-for-timing")


def check_login_secret(secret: str, stored: str | None) -> bool:
    """Verify a login secret; runs scrypt even when ``stored`` is None."""

    if stored is None:
        verify_secret(secret, _DUMMY_HASH)
        return False
    return verify_secret(secret, stored)


def require_token(x_api_token: str = Header(default="")) -> None:
    """Extra fixed-token guard for destructive endpoints (demo only).

    Applies only while ``ALLOW_DEMO_TOKEN`` is on (default in dev). It never
    identifies a user; the JWT does that via ``get_current_user``.
    """

    settings = get_settings()
    if not demo_token_enabled(settings):
        return
    expected = settings.demo_api_token
    if not hmac.compare_digest(
        x_api_token.encode("utf-8"), str(expected).encode("utf-8")
    ):
        raise HTTPException(status_code=401, detail="Invalid or missing API token")
