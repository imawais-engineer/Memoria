"""Readiness and metrics endpoints; no database or Redis needed."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core import observability
from app.main import app


@pytest.fixture
def client():
    import app.main as main_module

    main_module._ready_cache.clear()
    return TestClient(app)


def _patch(monkeypatch, db_ok: bool, redis_ok: bool) -> None:
    async def db() -> None:
        if not db_ok:
            raise RuntimeError("postgresql://user:secret@host/db refused")

    async def redis() -> None:
        if not redis_ok:
            raise RuntimeError("redis down")

    monkeypatch.setattr(observability, "check_database", db)
    monkeypatch.setattr(observability, "check_redis", redis)


def test_liveness_ok(client):
    assert client.get("/health").status_code == 200


def test_ready_ok(client, monkeypatch):
    _patch(monkeypatch, True, True)
    r = client.get("/health/ready")
    assert r.status_code == 200
    assert r.json() == {"status": "ready", "checks": {"database": "ok", "redis": "ok"}}


@pytest.mark.parametrize("db_ok,redis_ok", [(False, True), (True, False), (False, False)])
def test_ready_503_without_leaking_details(client, monkeypatch, db_ok, redis_ok):
    _patch(monkeypatch, db_ok, redis_ok)
    r = client.get("/health/ready")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "unavailable"
    assert "secret" not in r.text
    assert ("error" in body["checks"].values())


def test_metrics_text_format(client):
    client.get("/health")
    r = client.get("/metrics")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert "# TYPE memoria_http_requests_total counter" in r.text
    assert 'memoria_http_requests_total{method="GET",path="/health",status="200"}' in r.text
    assert "memoria_uptime_seconds" in r.text


def test_ready_is_cached_between_calls(client, monkeypatch):
    calls = {"n": 0}

    async def fake() -> dict[str, str]:
        calls["n"] += 1
        return {"database": "ok", "redis": "ok"}

    monkeypatch.setattr(observability, "run_readiness_checks", fake)
    assert client.get("/health/ready").status_code == 200
    assert client.get("/health/ready").status_code == 200
    assert calls["n"] == 1


def test_metrics_requires_token_when_configured(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "metrics_token", "s3cret-token")
    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer nope"}).status_code == 401
    ok = client.get("/metrics", headers={"Authorization": "Bearer s3cret-token"})
    assert ok.status_code == 200


def test_metrics_closed_outside_dev_without_token(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "environment", "production")
    monkeypatch.setattr(get_settings(), "metrics_token", "")
    assert client.get("/metrics").status_code == 403
