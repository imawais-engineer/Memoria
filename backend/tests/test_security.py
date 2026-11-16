"""DB-less tests for app.core.security."""

import pytest
from fastapi import HTTPException

from app.config import get_settings
from app.core.security import hash_secret, is_hashed, require_token, verify_secret


def test_hash_and_verify_roundtrip():
    stored = hash_secret("Blue Door")
    assert is_hashed(stored)
    assert stored.startswith("scrypt$")
    assert "Blue Door" not in stored
    assert verify_secret("Blue Door", stored)
    assert verify_secret("  blue door ", stored)  # case/whitespace-insensitive
    assert not verify_secret("red door", stored)


def test_hash_is_salted():
    assert hash_secret("same") != hash_secret("same")


def test_legacy_plaintext_still_verifies():
    assert not is_hashed("plain")
    assert verify_secret("plain", "plain")
    assert not verify_secret("other", "plain")


def test_malformed_hash_rejected():
    assert not verify_secret("x", "scrypt$nothex$nothex")
    assert not verify_secret("x", "scrypt$onlyonepart")


def test_require_token_accepts_configured_token():
    token = get_settings().demo_api_token
    assert require_token(x_api_token=token) is None


@pytest.mark.parametrize("bad", ["", "wrong-token"])
def test_require_token_rejects_bad_token(bad):
    with pytest.raises(HTTPException) as exc:
        require_token(x_api_token=bad)
    assert exc.value.status_code == 401


def test_legacy_plaintext_is_normalized_like_hashed():
    assert verify_secret("  DUNE ", "dune")


def test_check_login_secret_unknown_user_runs_scrypt(monkeypatch):
    from app.core import security

    calls = []
    real = security.verify_secret
    monkeypatch.setattr(
        security, "verify_secret", lambda s, h: calls.append(h) or real(s, h)
    )
    assert security.check_login_secret("x", None) is False
    assert calls == [security._DUMMY_HASH]
    assert security.check_login_secret("Blue", hash_secret("blue")) is True
    assert security.check_login_secret("red", hash_secret("blue")) is False
