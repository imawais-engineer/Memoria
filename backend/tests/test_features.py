"""Tests for memorize, tasks, and streaming chat endpoints."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.core.redis_client import get_redis
from app.main import app
from app.models.user import User


@pytest.mark.asyncio
async def test_memorize_creates_core_memory(db_session_factory):
    async with db_session_factory() as session:
        user = User(
            username="mem_user",
            first_name="Mem",
            last_name="User",
            favorite_book="Dune",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = str(user.id)

    async def override_get_db():
        async with db_session_factory() as db:
            yield db

    mock_redis = AsyncMock()

    async def override_get_redis():
        return mock_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    with patch("app.api.memorize.get_embedding", new=AsyncMock(return_value=[0.1] * 1024)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/memorize",
                json={"user_id": user_id, "content": "I love hiking"},
            )

    app.dependency_overrides.clear()

    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["id"]


@pytest.mark.asyncio
async def test_create_and_list_tasks(db_session_factory):
    async with db_session_factory() as session:
        user = User(
            username="task_user",
            first_name="Task",
            last_name="User",
            favorite_book="1984",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = str(user.id)

    async def override_get_db():
        async with db_session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db

    with patch("app.api.tasks.get_embedding", new=AsyncMock(return_value=[0.1] * 1024)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            create_res = await client.post(
                "/api/tasks",
                json={"user_id": user_id, "title": "Buy groceries"},
            )
            list_res = await client.get(f"/api/tasks?user_id={user_id}")

    app.dependency_overrides.clear()

    assert create_res.status_code == 200
    created = create_res.json()
    assert created["title"] == "Buy groceries"
    assert created["status"] == "pending"

    assert list_res.status_code == 200
    tasks = list_res.json()
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Buy groceries"


@pytest.mark.asyncio
async def test_chat_stream_endpoint(db_session_factory):
    async with db_session_factory() as session:
        user = User(
            username="stream_user",
            first_name="Stream",
            last_name="User",
            favorite_book="Neuromancer",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = str(user.id)

    async def override_get_db():
        async with db_session_factory() as db:
            yield db

    mock_redis = AsyncMock()
    mock_redis.lrange.return_value = []
    mock_redis.get.return_value = None
    mock_redis.rpush = AsyncMock()
    mock_redis.ltrim = AsyncMock()
    mock_redis.expire = AsyncMock()
    mock_redis.incr.return_value = 1

    async def override_get_redis():
        return mock_redis

    async def fake_stream(*_args, **_kwargs):
        yield "Hello"
        yield " world"

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    with (
        patch("app.services.agent_service.stream_qwen_chat", new=fake_stream),
        patch(
            "app.services.agent_service.retrieve_context_and_ids",
            new=AsyncMock(return_value=("", [])),
        ),
        patch(
            "app.services.agent_service.get_latest_reflection",
            new=AsyncMock(return_value=None),
        ),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/chat/stream",
                json={"user_id": user_id, "message": "Hi there"},
            )

    app.dependency_overrides.clear()

    assert res.status_code == 200
    assert "text/event-stream" in res.headers.get("content-type", "")

    events = []
    for block in res.text.strip().split("\n\n"):
        if block.startswith("data: "):
            events.append(json.loads(block[6:]))

    tokens = [e["token"] for e in events if "token" in e]
    assert "".join(tokens) == "Hello world"
    assert any(e.get("done") for e in events)
