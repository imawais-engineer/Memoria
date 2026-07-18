"""Tests for memory list and stats filtering on the Memories page."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.memory.models import Memory
from app.models.chat_session import ChatSession
from app.models.user import User


def _memory(
    *,
    user_id: str,
    content: str,
    session_id: uuid.UUID | None = None,
    archived: bool = False,
    superseded: bool = False,
) -> Memory:
    return Memory(
        user_id=user_id,
        type="episodic",
        content=content,
        embedding=[0.0] * 1024,
        importance=0.8,
        session_id=session_id,
        archived=archived,
        superseded=superseded,
    )


@pytest.mark.asyncio
async def test_list_memories_returns_all_active_across_chats(
    client: AsyncClient,
    db_session_factory,
):
    user_id = uuid.uuid4()
    session_a = uuid.uuid4()
    session_b = uuid.uuid4()
    memoryless_session = uuid.uuid4()

    async with db_session_factory() as db:
        db.add(
            User(
                id=user_id,
                username=f"mem_{user_id.hex[:8]}",
                first_name="Test",
                last_name="User",
                favorite_book="Dune",
            )
        )
        await db.flush()
        db.add_all(
            [
                ChatSession(id=session_a, user_id=user_id, title="Chat A"),
                ChatSession(id=session_b, user_id=user_id, title="Chat B"),
                ChatSession(
                    id=memoryless_session,
                    user_id=user_id,
                    title="MemoryLess",
                    is_memoryless=True,
                ),
            ]
        )
        await db.flush()
        db.add_all(
            [
                _memory(user_id=str(user_id), content="From chat A", session_id=session_a),
                _memory(user_id=str(user_id), content="From chat B", session_id=session_b),
                _memory(
                    user_id=str(user_id),
                    content="Global core fact",
                    session_id=None,
                ),
                _memory(
                    user_id=str(user_id),
                    content="MemoryLess only",
                    session_id=memoryless_session,
                ),
                _memory(
                    user_id=str(user_id),
                    content="Forgotten",
                    session_id=session_a,
                    archived=True,
                ),
                _memory(
                    user_id=str(user_id),
                    content="Superseded",
                    session_id=session_b,
                    superseded=True,
                ),
            ]
        )
        await db.commit()

    res = await client.get("/api/memories", params={"user_id": str(user_id)})
    assert res.status_code == 200
    contents = {item["content"] for item in res.json()}
    assert contents == {"From chat A", "From chat B", "Global core fact"}


@pytest.mark.asyncio
async def test_memory_stats_exclude_forgotten_and_memoryless(
    client: AsyncClient,
    db_session_factory,
):
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    memoryless_session = uuid.uuid4()

    async with db_session_factory() as db:
        db.add(
            User(
                id=user_id,
                username=f"stats_{user_id.hex[:8]}",
                first_name="Test",
                last_name="User",
                favorite_book="Dune",
            )
        )
        await db.flush()
        db.add_all(
            [
                ChatSession(id=session_id, user_id=user_id, title="Chat"),
                ChatSession(
                    id=memoryless_session,
                    user_id=user_id,
                    title="MemoryLess",
                    is_memoryless=True,
                ),
            ]
        )
        await db.flush()
        db.add_all(
            [
                _memory(user_id=str(user_id), content="Visible", session_id=session_id),
                _memory(
                    user_id=str(user_id),
                    content="Hidden memoryless",
                    session_id=memoryless_session,
                ),
                _memory(
                    user_id=str(user_id),
                    content="Hidden archived",
                    session_id=session_id,
                    archived=True,
                ),
            ]
        )
        await db.commit()

    res = await client.get(
        "/api/memory-stats",
        params={"user_id": str(user_id)},
        headers={"X-API-Token": "memoria-demo-token"},
    )
    assert res.status_code == 200
    assert res.json()["total_memories"] == 1
