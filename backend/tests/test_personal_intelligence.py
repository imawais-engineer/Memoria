"""Tests for Personal Intelligence memory scoping."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.memory.models import Memory
from app.memory.retrieval import retrieve_context_and_ids
from app.models.chat_session import ChatSession
from app.models.user import User

EMBEDDING = [1.0] + [0.0] * 1023


def _memory(
    *,
    user_id: str,
    content: str,
    session_id: uuid.UUID | None = None,
    memory_type: str = "episodic",
) -> Memory:
    return Memory(
        user_id=user_id,
        type=memory_type,
        content=content,
        embedding=EMBEDDING,
        importance=0.9,
        session_id=session_id,
    )


@pytest.mark.asyncio
async def test_pi_on_retrieves_memories_from_all_sessions(db_session_factory):
    user_id = uuid.uuid4()
    session_a = uuid.uuid4()
    session_b = uuid.uuid4()

    async with db_session_factory() as db:
        db.add(
            User(
                id=user_id,
                username=f"pi_on_{user_id.hex[:8]}",
                first_name="Test",
                last_name="User",
                favorite_book="Dune",
                global_memory_enabled=True,
            )
        )
        await db.flush()
        db.add_all(
            [
                ChatSession(id=session_a, user_id=user_id, title="Chat A"),
                ChatSession(id=session_b, user_id=user_id, title="Chat B"),
            ]
        )
        await db.flush()
        db.add_all(
            [
                _memory(
                    user_id=str(user_id),
                    content="Likes hiking",
                    session_id=session_a,
                ),
                _memory(
                    user_id=str(user_id),
                    content="Prefers tea",
                    session_id=session_b,
                ),
            ]
        )
        await db.commit()

        with patch(
            "app.memory.retrieval.get_embedding",
            new=AsyncMock(return_value=EMBEDDING),
        ):
            context, memory_ids = await retrieve_context_and_ids(
                str(user_id),
                "What do I like?",
                db_session=db,
                session_id=str(session_b),
                global_memory_enabled=True,
            )

    assert "Likes hiking" in context
    assert "Prefers tea" in context
    assert len(memory_ids) == 2


@pytest.mark.asyncio
async def test_pi_off_limits_to_current_session_plus_manual_core(db_session_factory):
    user_id = uuid.uuid4()
    session_a = uuid.uuid4()
    session_b = uuid.uuid4()

    async with db_session_factory() as db:
        db.add(
            User(
                id=user_id,
                username=f"pi_off_{user_id.hex[:8]}",
                first_name="Test",
                last_name="User",
                favorite_book="Dune",
                global_memory_enabled=False,
            )
        )
        await db.flush()
        db.add_all(
            [
                ChatSession(id=session_a, user_id=user_id, title="Chat A"),
                ChatSession(id=session_b, user_id=user_id, title="Chat B"),
            ]
        )
        await db.flush()
        db.add_all(
            [
                _memory(
                    user_id=str(user_id),
                    content="Old chat: allergic to peanuts",
                    session_id=session_a,
                ),
                _memory(
                    user_id=str(user_id),
                    content="Current chat: planning a trip",
                    session_id=session_b,
                ),
                _memory(
                    user_id=str(user_id),
                    content="Manual core: vegetarian",
                    session_id=None,
                    memory_type="core",
                ),
            ]
        )
        await db.commit()

        with patch(
            "app.memory.retrieval.get_embedding",
            new=AsyncMock(return_value=EMBEDDING),
        ):
            context, memory_ids = await retrieve_context_and_ids(
                str(user_id),
                "What should I eat?",
                db_session=db,
                session_id=str(session_b),
                global_memory_enabled=False,
            )

    assert "Current chat: planning a trip" in context
    assert "Manual core: vegetarian" in context
    assert "Old chat: allergic to peanuts" not in context
    assert len(memory_ids) == 2


@pytest.mark.asyncio
async def test_memoryless_retrieves_no_long_term_memories(db_session_factory):
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()

    async with db_session_factory() as db:
        db.add(
            User(
                id=user_id,
                username=f"ml_{user_id.hex[:8]}",
                first_name="Test",
                last_name="User",
                favorite_book="Dune",
            )
        )
        await db.flush()
        db.add(ChatSession(id=session_id, user_id=user_id, title="MemoryLess", is_memoryless=True))
        await db.flush()
        db.add(
            _memory(
                user_id=str(user_id),
                content="Should not appear",
                session_id=session_id,
            )
        )
        await db.commit()

        with patch(
            "app.memory.retrieval.get_embedding",
            new=AsyncMock(return_value=EMBEDDING),
        ):
            context, memory_ids = await retrieve_context_and_ids(
                str(user_id),
                "What do you know?",
                db_session=db,
                session_id=str(session_id),
                is_memoryless=True,
            )

    assert context == ""
    assert memory_ids == []


@pytest.mark.asyncio
async def test_prepare_chat_turn_skips_reflection_when_pi_off(
    db_session_factory,
):
    from app.services.agent_service import _prepare_chat_turn

    user_id = uuid.uuid4()
    session_id = uuid.uuid4()

    async with db_session_factory() as db:
        db.add(
            User(
                id=user_id,
                username=f"refl_{user_id.hex[:8]}",
                first_name="Test",
                last_name="User",
                favorite_book="Dune",
                global_memory_enabled=False,
            )
        )
        await db.flush()
        db.add(ChatSession(id=session_id, user_id=user_id, title="Chat"))
        await db.commit()

    mock_redis = AsyncMock()
    mock_redis.lrange.return_value = []

    async with db_session_factory() as db:
        with (
            patch(
                "app.services.agent_service.retrieve_context_and_ids",
                new=AsyncMock(return_value=("", [])),
            ),
            patch(
                "app.services.agent_service.get_latest_reflection",
                new=AsyncMock(return_value="Global reflection text"),
            ) as mock_reflection,
            patch(
                "app.services.agent_service.touch_session_on_message",
                new=AsyncMock(return_value=None),
            ),
        ):
            prepared = await _prepare_chat_turn(
                str(user_id),
                "Hello",
                str(session_id),
                is_memoryless=False,
                db_session=db,
                redis_client=mock_redis,
            )

    mock_reflection.assert_not_awaited()
    system_prompt = prepared["messages"][0]["content"]
    assert "Global reflection text" not in system_prompt
    assert "Personal Intelligence is OFF" in system_prompt
