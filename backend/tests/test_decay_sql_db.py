"""Run the decay (forgetting) SQL against a database built by ``alembic upgrade head``.

CI applies migrations first, then runs this file. It skips when the database is
unreachable or has not been migrated, so it is a no-op for local runs.
"""

from __future__ import annotations

import math
import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.memory.forgetting import ARCHIVE_THRESHOLD, apply_decay, decayed_importance

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/memoria"
)
USER_ID = f"decay-sql-{uuid.uuid4()}"
VECTOR = "[" + ",".join(["0.1"] * 1024) + "]"


@pytest_asyncio.fixture
async def migrated_session():
    engine = create_async_engine(TEST_DATABASE_URL)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT version_num FROM alembic_version"))
    except Exception as exc:  # noqa: BLE001
        await engine.dispose()
        pytest.skip(f"Migrated database unavailable ({type(exc).__name__})")
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.execute(text("DELETE FROM memories WHERE user_id = :u"), {"u": USER_ID})
        await session.commit()
    await engine.dispose()


async def _insert(session, mtype: str, importance: float, rate: float, age_days: int) -> str:
    mem_id = str(uuid.uuid4())
    await session.execute(
        text(
            "INSERT INTO memories (id, user_id, type, content, embedding, importance, "
            "decay_rate, created_at) VALUES (:id, :u, :t, 'x', CAST(:v AS vector), :imp, "
            ":rate, NOW() - make_interval(days => :age))"
        ),
        {"id": mem_id, "u": USER_ID, "t": mtype, "v": VECTOR, "imp": importance,
         "rate": rate, "age": age_days},
    )
    await session.commit()
    return mem_id


async def _row(session, mem_id: str):
    res = await session.execute(
        text("SELECT importance, archived, last_decayed_at FROM memories WHERE id = :id"),
        {"id": mem_id},
    )
    return res.one()


async def test_decay_matches_python_formula(migrated_session):
    mem_id = await _insert(migrated_session, "semantic", 0.8, 0.02, 10)
    await apply_decay(migrated_session)
    importance, archived, last = await _row(migrated_session, mem_id)
    assert importance == pytest.approx(decayed_importance(0.8, 0.02, 10), rel=1e-3)
    assert not archived and last is not None


async def test_core_memories_are_untouched(migrated_session):
    mem_id = await _insert(migrated_session, "core", 0.9, 0.5, 365)
    await apply_decay(migrated_session)
    importance, archived, last = await _row(migrated_session, mem_id)
    assert importance == pytest.approx(0.9) and not archived and last is None


async def test_weak_memories_are_archived_and_decay_does_not_compound(migrated_session):
    weak = await _insert(migrated_session, "episodic", 0.3, 0.1, 30)
    steady = await _insert(migrated_session, "semantic", 1.0, 0.01, 10)
    await apply_decay(migrated_session)
    first = (await _row(migrated_session, steady))[0]
    await apply_decay(migrated_session)  # immediately again: ~no extra decay
    second = (await _row(migrated_session, steady))[0]
    assert second == pytest.approx(first, rel=1e-3)
    assert first == pytest.approx(math.exp(-0.1), rel=1e-3)
    importance, archived, _ = await _row(migrated_session, weak)
    assert importance < ARCHIVE_THRESHOLD and archived
