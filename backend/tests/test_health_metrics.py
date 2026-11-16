"""Readiness and metrics endpoints; no database or Redis needed."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core import observability
from app.main import app


@pytest.fixture
def client():
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
