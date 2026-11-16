"""DB-less tests: JWT auth, per-user isolation, rate limits and token caps."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import jwt
import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.config import Settings, validate_runtime_settings
from app.core.auth import (
    ALGORITHM,
    authorize_claimed_user,
    create_access_token,
    decode_access_token,
)
from app.core.database import get_db
from app.main import app
from app.services import limits
from app.services.limits import Limiter, MemoryCounterStore, estimate_tokens, get_limiter

ALICE = str(uuid.uuid4())
BOB = str(uuid.uuid4())


def bearer(user_id: str, **kw) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id, **kw)}"}


class ExplodingDB:
    """Any DB access means a route did not stop at the auth check."""

    def __getattr__(self, name):
        raise AssertionError(f"DB touched: {name}")


class FakeDB:
    def __init__(self, rows=None):
        self.rows = rows or {}
        self.committed = False

    async def get(self, model, key):
        return self.rows.get(key)

    async def commit(self):
        self.committed = True


@pytest.fixture
async def api():
    holder = {"db": ExplodingDB()}

    async def override_db():
        yield holder["db"]

    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        ac.holder = holder
        yield ac
    app.dependency_overrides.clear()


# --- token issue / verify -------------------------------------------------


def test_token_roundtrip():
    assert decode_access_token(create_access_token(ALICE)) == ALICE


def test_expired_token_rejected():
    token = create_access_token(ALICE, ttl_minutes=-1)
    with pytest.raises(HTTPException) as exc:
        decode_access_token(token)
    assert exc.value.status_code == 401


def test_wrong_key_and_alg_none_rejected():
    forged = jwt.encode({"sub": ALICE, "iss": "memoria", "exp": 9999999999}, "x" * 40, ALGORITHM)
    unsigned = jwt.encode({"sub": ALICE, "iss": "memoria", "exp": 9999999999}, None, "none")
    for token in (forged, unsigned, "garbage"):
        with pytest.raises(HTTPException) as exc:
            decode_access_token(token)
        assert exc.value.status_code == 401


def test_non_uuid_subject_rejected():
    token = create_access_token("not-a-uuid")
    with pytest.raises(HTTPException):
        decode_access_token(token)


def test_authorize_claimed_user():
    assert authorize_claimed_user(None, ALICE) == ALICE
    assert authorize_claimed_user(ALICE.upper(), ALICE) == ALICE
    with pytest.raises(HTTPException) as exc:
        authorize_claimed_user(BOB, ALICE)
    assert exc.value.status_code == 403


def test_default_secret_refused_outside_dev():
    validate_runtime_settings(Settings(_env_file=None, environment="dev"))
    # Fails closed: no ENVIRONMENT set means production rules apply.
    with pytest.raises(RuntimeError):
        validate_runtime_settings(Settings(_env_file=None, environment="production"))
    with pytest.raises(RuntimeError):
        validate_runtime_settings(
            Settings(_env_file=None, environment="production", secret_key="short")
        )
    validate_runtime_settings(
        Settings(_env_file=None, environment="production", secret_key="k" * 40)
    )


# --- routes reject missing / invalid tokens ------------------------------

PROTECTED = [
    ("get", "/api/memories"),
    ("get", "/api/memory-stats"),
    ("delete", f"/api/memories/{uuid.uuid4()}"),
    ("get", "/api/search-archive?query=x"),
    ("post", "/api/memorize"),
    ("post", "/api/feedback"),
    ("post", "/api/tasks"),
    ("get", "/api/tasks"),
    ("patch", f"/api/tasks/{uuid.uuid4()}"),
    ("delete", f"/api/tasks/{uuid.uuid4()}"),
    ("post", "/sessions"),
    ("get", "/sessions"),
    ("get", f"/sessions/{uuid.uuid4()}/history"),
    ("patch", f"/sessions/{uuid.uuid4()}"),
    ("delete", f"/sessions/{uuid.uuid4()}"),
    ("post", "/chat"),
    ("post", "/chat/stream"),
    ("post", "/api/generate/image"),
    ("post", "/api/generate/video"),
    ("post", "/api/generate/voice"),
    ("get", "/api/generate/assets"),
    ("delete", f"/api/generate/assets/{uuid.uuid4()}"),
    ("get", "/auth/preferences"),
    ("patch", "/auth/preferences"),
]


@pytest.mark.parametrize("method,path", PROTECTED)
@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer nope"}, {"X-API-Token": "memoria-demo-token"}])
async def test_routes_reject_missing_or_invalid_token(api, method, path, headers):
    res = await api.request(method, path, headers=headers, json={})
    assert res.status_code == 401, (method, path, res.text)


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("get", f"/api/memories?user_id={BOB}", None),
        ("get", f"/api/memory-stats?user_id={BOB}", None),
        ("delete", f"/api/memories/{uuid.uuid4()}?user_id={BOB}", None),
        ("get", f"/api/search-archive?user_id={BOB}&query=x", None),
        ("post", "/api/memorize", {"user_id": BOB, "content": "x"}),
        ("post", "/api/feedback", {"user_id": BOB, "memory_ids": [], "rating": "positive"}),
        ("post", "/api/tasks", {"user_id": BOB, "title": "t"}),
        ("get", f"/api/tasks?user_id={BOB}", None),
        ("post", "/sessions", {"user_id": BOB}),
        ("get", f"/sessions?user_id={BOB}", None),
        ("get", f"/sessions/{uuid.uuid4()}/history?user_id={BOB}", None),
        ("patch", f"/sessions/{uuid.uuid4()}?user_id={BOB}", {"title": "x"}),
        ("delete", f"/sessions/{uuid.uuid4()}?user_id={BOB}", None),
        ("post", "/chat", {"user_id": BOB, "message": "hi"}),
        ("post", "/chat/stream", {"user_id": BOB, "message": "hi"}),
        ("post", "/api/generate/image", {"user_id": BOB, "prompt": "p"}),
        ("get", f"/api/generate/assets?user_id={BOB}", None),
        ("delete", f"/api/generate/assets/{uuid.uuid4()}?user_id={BOB}", None),
        ("get", f"/auth/preferences?user_id={BOB}", None),
        ("patch", "/auth/preferences", {"user_id": BOB, "global_memory_enabled": False}),
    ],
)
async def test_cross_user_access_denied(api, method, path, body):
    """Alice's token cannot act on Bob's user_id; DB is never reached."""

    kwargs = {"json": body} if body is not None else {}
    res = await api.request(
        method, path, headers={**bearer(ALICE), "X-API-Token": "memoria-demo-token"}, **kwargs
    )
    assert res.status_code == 403, (method, path, res.text)


async def test_task_ownership_enforced_on_update_and_delete(api):
    task_id = uuid.uuid4()
    bobs_task = SimpleNamespace(id=task_id, user_id=uuid.UUID(BOB), status="open")
    api.holder["db"] = FakeDB({task_id: bobs_task})
    res = await api.patch(
        f"/api/tasks/{task_id}", json={"status": "done"}, headers=bearer(ALICE)
    )
    assert res.status_code == 404
    assert bobs_task.status == "open"


async def test_user_id_not_required_when_token_present(api):
    api.holder["db"] = FakeDB()
    res = await api.post(
        "/api/memorize", json={"content": "x"}, headers=bearer(ALICE)
    )
    assert res.status_code == 404  # reached the DB lookup as Alice


# --- rate limit and token cap --------------------------------------------


async def test_rate_limit_allows_then_429():
    limiter = Limiter(None)
    for _ in range(3):
        await limiter.check_rate(ALICE, 3)
    with pytest.raises(HTTPException) as exc:
        await limiter.check_rate(ALICE, 3)
    assert exc.value.status_code == 429
    await limiter.check_rate(BOB, 3)  # other users unaffected


async def test_rate_limit_zero_disables():
    limiter = Limiter(None)
    for _ in range(5):
        await limiter.check_rate(ALICE, 0)


async def test_token_cap():
    limiter = Limiter(None)
    await limiter.check_token_cap(ALICE, 100)
    await limiter.add_tokens(ALICE, 100)
    with pytest.raises(HTTPException) as exc:
        await limiter.check_token_cap(ALICE, 100)
    assert exc.value.status_code == 429
    await limiter.check_token_cap(BOB, 100)


def test_memory_store_expiry(monkeypatch):
    store = MemoryCounterStore()
    now = [100.0]
    monkeypatch.setattr(limits.time, "monotonic", lambda: now[0])
    assert store.incr("k", 1, 10) == 1
    assert store.incr("k", 1, 10) == 2
    now[0] = 111.0
    assert store.get("k") == 0
    assert store.incr("k", 1, 10) == 1


class FakeRedis:
    def __init__(self):
        self.data: dict[str, int] = {}
        self.expiry: dict[str, int] = {}

    async def incrby(self, key, amount):
        self.data[key] = self.data.get(key, 0) + amount
        return self.data[key]

    async def expire(self, key, ttl):
        self.expiry[key] = ttl

    async def get(self, key):
        return self.data.get(key)

    def pipeline(self, transaction=True):
        return FakePipeline(self)


class FakePipeline:
    def __init__(self, redis):
        self.redis = redis
        self.ops = []

    def incrby(self, key, amount):
        self.ops.append(("incrby", key, amount))

    def expire(self, key, ttl):
        self.ops.append(("expire", key, ttl))

    async def execute(self):
        out = []
        for name, *args in self.ops:
            out.append(await getattr(self.redis, name)(*args))
        return out


class BrokenRedis:
    def pipeline(self, transaction=True):
        raise ConnectionError("down")

    async def get(self, *a):
        raise ConnectionError("down")


async def test_redis_backend_used_and_expiry_set():
    redis = FakeRedis()
    limiter = Limiter(redis)
    await limiter.add_tokens(ALICE, 5)
    assert list(redis.data.values()) == [5]
    assert list(redis.expiry.values()) == [2 * 24 * 3600]
    assert limiter.fallback.get(next(iter(redis.data))) == 0


async def test_falls_back_to_memory_when_redis_down():
    limiter = Limiter(BrokenRedis())
    await limiter.check_rate(ALICE, 1)
    with pytest.raises(HTTPException):
        await limiter.check_rate(ALICE, 1)


def test_estimate_tokens():
    assert estimate_tokens("a" * 40) == 10
    assert estimate_tokens("") == 0


async def test_route_returns_429_when_rate_limited(api, monkeypatch):
    monkeypatch.setattr(limits, "get_settings", lambda: SimpleNamespace(rate_limit_per_min=1, daily_token_cap=0))
    api.holder["db"] = FakeDB()
    shared = Limiter(None)
    app.dependency_overrides[get_limiter] = lambda: shared
    try:
        first = await api.post("/api/memorize", json={"content": "x"}, headers=bearer(ALICE))
        second = await api.post("/api/memorize", json={"content": "x"}, headers=bearer(ALICE))
    finally:
        app.dependency_overrides.pop(get_limiter, None)
    assert first.status_code == 404
    assert second.status_code == 429
    assert "Retry-After" in second.headers


async def test_route_returns_429_when_token_cap_hit(api, monkeypatch):
    monkeypatch.setattr(limits, "get_settings", lambda: SimpleNamespace(rate_limit_per_min=0, daily_token_cap=10))
    limiter = Limiter(None)
    await limiter.add_tokens(ALICE, 10)
    app.dependency_overrides[get_limiter] = lambda: limiter
    try:
        res = await api.post("/api/memorize", json={"content": "x"}, headers=bearer(ALICE))
    finally:
        app.dependency_overrides.pop(get_limiter, None)
    assert res.status_code == 429


def test_environment_defaults_to_production(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    cfg = Settings(_env_file=None)
    assert cfg.environment == "production"
    with pytest.raises(RuntimeError):
        validate_runtime_settings(cfg)


async def test_expiry_set_on_every_increment():
    redis = FakeRedis()
    limiter = Limiter(redis)
    await limiter.check_rate(ALICE, 10)
    key = next(iter(redis.data))
    redis.expiry.clear()  # simulate a lost TTL
    await limiter.check_rate(ALICE, 10)
    assert redis.expiry[key] == 61


async def test_mcp_limits_apply_rate_and_cap(monkeypatch):
    from app.config import get_settings
    from app.services.limits import charge_mcp_tokens, enforce_mcp_limits

    monkeypatch.setattr(get_settings(), "rate_limit_per_min", 2)
    monkeypatch.setattr(get_settings(), "daily_token_cap", 10)
    limiter = Limiter(None)
    await enforce_mcp_limits(ALICE, limiter)
    await charge_mcp_tokens(ALICE, 10, limiter)
    with pytest.raises(ValueError, match="Daily token limit"):
        await enforce_mcp_limits(ALICE, limiter)
    monkeypatch.setattr(get_settings(), "daily_token_cap", 0)
    with pytest.raises(ValueError, match="Rate limit"):
        await enforce_mcp_limits(ALICE, limiter)


async def test_stream_charges_tokens_on_failure(api, monkeypatch):
    from app.api import chat as chat_module
    from app.services.limits import get_limiter

    async def boom(*a, **k):
        yield {"type": "token", "token": "x" * 40}
        raise RuntimeError("provider died")

    limiter = Limiter(None)
    async def no_limit(*a, **k):
        return None

    monkeypatch.setattr(chat_module, "handle_message_stream", boom)
    monkeypatch.setattr(chat_module, "_enforce_message_limit", no_limit)
    app.dependency_overrides[get_limiter] = lambda: limiter
    try:
        res = await api.post(
            "/chat/stream",
            json={"message": "hi there", "user_id": ALICE},
            headers={"Authorization": f"Bearer {create_access_token(ALICE)}"},
        )
    finally:
        app.dependency_overrides.pop(get_limiter, None)
    assert "provider died" in res.text
    assert await limiter._get(limiter._day_key(ALICE)) >= 10
