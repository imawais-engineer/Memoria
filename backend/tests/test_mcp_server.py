"""MCP server tests: tool handlers with fakes, auth, and the HTTP mount."""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.auth import create_access_token
from app.mcp import server as srv

USER = str(uuid.uuid4())


class FakeDB:
    def __init__(self, rowcount: int = 1) -> None:
        self.rowcount = rowcount
        self.executed: list = []
        self.commits = 0

    async def execute(self, stmt):
        self.executed.append(stmt)
        return SimpleNamespace(rowcount=self.rowcount)

    async def commit(self):
        self.commits += 1


async def test_remember_stores_via_ingestion(monkeypatch):
    seen = {}

    async def fake_extract(text, user_id, message_id, db, session_id=None, **_):
        seen.update(text=text, user_id=user_id, message_id=message_id)
        return [SimpleNamespace(id=uuid.uuid4(), type="preference", kind="fact", content="likes tea")]

    monkeypatch.setattr(srv, "extract_and_store_memories", fake_extract)
    out = await srv.remember_handler(USER, " I like tea ", FakeDB())
    assert out["stored"] == 1 and out["memories"][0]["content"] == "likes tea"
    assert seen["user_id"] == USER and seen["text"] == "I like tea"
    assert seen["message_id"].startswith("mcp-")


async def test_remember_rejects_empty_and_oversized():
    with pytest.raises(ValueError):
        await srv.remember_handler(USER, "  ", FakeDB())
    with pytest.raises(ValueError):
        await srv.remember_handler(USER, "x" * (srv.MAX_TEXT_CHARS + 1), FakeDB())


async def test_recall_returns_why(monkeypatch):
    async def fake_retrieve(user_id, query, db_session=None, include_superseded=False, **_):
        assert user_id == USER and include_superseded is True
        return [{"id": "1", "content": "likes tea", "why": {"similarity": 0.9}}]

    monkeypatch.setattr(srv, "retrieve_with_why", fake_retrieve)
    out = await srv.recall_handler(USER, "drink?", FakeDB(), include_superseded=True)
    assert out["count"] == 1 and out["memories"][0]["why"]["similarity"] == 0.9
    with pytest.raises(ValueError):
        await srv.recall_handler(USER, "", FakeDB())


async def test_forget_scopes_to_user_and_reports_result():
    db = FakeDB(rowcount=1)
    mid = str(uuid.uuid4())
    out = await srv.forget_handler(USER, mid, db)
    assert out == {"forgotten": True, "memory_id": mid} and db.commits == 1
    compiled = db.executed[0].compile().params
    assert USER in compiled.values()
    assert (await srv.forget_handler(USER, mid, FakeDB(rowcount=0)))["forgotten"] is False
    with pytest.raises(ValueError):
        await srv.forget_handler(USER, "not-a-uuid", db)


def test_resolve_user_from_env(monkeypatch):
    monkeypatch.delenv("MEMORIA_MCP_TOKEN", raising=False)
    monkeypatch.delenv("MEMORIA_MCP_USER_ID", raising=False)
    with pytest.raises(srv.MCPAuthError):
        srv.resolve_user_id()
    monkeypatch.setenv("MEMORIA_MCP_USER_ID", USER)
    assert srv.resolve_user_id() == USER
    monkeypatch.setenv("MEMORIA_MCP_USER_ID", "bad")
    with pytest.raises(srv.MCPAuthError):
        srv.resolve_user_id()
    monkeypatch.setenv("MEMORIA_MCP_TOKEN", create_access_token(USER))
    assert srv.resolve_user_id() == USER
    monkeypatch.setenv("MEMORIA_MCP_TOKEN", "garbage")
    with pytest.raises(srv.MCPAuthError):
        srv.resolve_user_id()


def _app() -> FastAPI:
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan(a):
        async with a.state.mcp_server.session_manager.run():
            yield

    app = FastAPI(lifespan=lifespan)
    srv.mount_mcp(app)
    return app


def test_http_requires_bearer_token():
    app = _app()
    with TestClient(app) as client:
        r = client.post("/mcp/", json={})
        assert r.status_code == 401
        r = client.post("/mcp/", json={}, headers={"Authorization": "Bearer nope"})
        assert r.status_code == 401


def test_http_lists_and_calls_tools(monkeypatch):
    async def fake_recall(user_id, query, db, include_superseded=False):
        return {"count": 0, "memories": [], "user": user_id}

    class _S:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(srv, "recall_handler", fake_recall)
    monkeypatch.setattr(srv, "open_session", lambda: _S())
    app = _app()
    h = {
        "Authorization": f"Bearer {create_access_token(USER)}",
        "Accept": "application/json, text/event-stream",
    }
    with TestClient(app) as client:
        r = client.post("/mcp/", headers=h, json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                       "clientInfo": {"name": "t", "version": "0"}}})
        assert r.status_code == 200, r.text
        r = client.post("/mcp/", headers=h, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        names = {t["name"] for t in r.json()["result"]["tools"]}
        assert names == {"remember", "recall", "forget"}
        r = client.post("/mcp/", headers=h, json={
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "recall", "arguments": {"query": "tea"}}})
        payload = json.loads(r.json()["result"]["content"][0]["text"])
        assert payload["user"] == USER


@pytest.mark.asyncio
async def test_remember_charges_tokens_on_failure_and_includes_memories(monkeypatch):
    charged = []

    async def fake_enforce(user_id, limiter=None):
        return None

    async def fake_charge(user_id, tokens, limiter=None):
        charged.append(tokens)

    class _S:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(srv, "enforce_mcp_limits", fake_enforce)
    monkeypatch.setattr(srv, "charge_mcp_tokens", fake_charge)
    monkeypatch.setattr(srv, "open_session", lambda: _S())
    monkeypatch.setenv("MEMORIA_MCP_USER_ID", USER)
    server = srv.build_server()

    async def ok(user_id, text, db, session_id=None):
        return {"stored": 1, "memories": [{"content": "x" * 400}]}

    monkeypatch.setattr(srv, "remember_handler", ok)
    await server.call_tool("remember", {"text": "hi"})
    assert charged[-1] == srv.estimate_tokens("hi", "x" * 400)
    assert charged[-1] > srv.estimate_tokens("hi")

    async def boom(user_id, text, db, session_id=None):
        raise RuntimeError("provider down")

    monkeypatch.setattr(srv, "remember_handler", boom)
    with pytest.raises(Exception):
        await server.call_tool("remember", {"text": "hi"})
    assert charged[-1] == srv.estimate_tokens("hi")
