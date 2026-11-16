"""DB-less tests for ingestion parsing and decay-rate mapping (mocked Qwen/embeddings)."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.memory import ingestion
from app.memory.ingestion import (
    DECAY_RATES,
    DEFAULT_DECAY_RATE,
    _extract_tool_arguments,
    extract_and_store_memories,
)


def _response(arguments):
    return SimpleNamespace(
        output={
            "choices": [
                {"message": {"tool_calls": [{"function": {"arguments": arguments}}]}}
            ]
        }
    )


def test_parses_json_string_arguments():
    args = {"memories": [{"content": "likes tea", "type": "preference"}]}
    assert _extract_tool_arguments(_response(json.dumps(args))) == args


def test_parses_dict_arguments():
    args = {"memories": []}
    assert _extract_tool_arguments(_response(args)) == args


def test_bad_inputs_return_none():
    assert _extract_tool_arguments(_response("{not json")) is None
    assert _extract_tool_arguments(_response("")) is None
    assert _extract_tool_arguments(SimpleNamespace(output={})) is None
    no_calls = SimpleNamespace(output={"choices": [{"message": {"content": "hi"}}]})
    assert _extract_tool_arguments(no_calls) is None


def test_decay_rates_by_type():
    assert DECAY_RATES["core"] == 0.0
    assert DECAY_RATES["episodic"] > DECAY_RATES["semantic"] > DECAY_RATES["procedural"]
    assert DEFAULT_DECAY_RATE == 0.01


def _db():
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


async def test_store_assigns_decay_rate_by_type(monkeypatch):
    items = [
        {"content": "name is Sam", "type": "core", "importance": 0.9, "expires_in_hours": 0},
        {"content": "met Bob today", "type": "episodic", "importance": 0.4, "expires_in_hours": 24},
        {"content": "odd", "type": "unknown", "importance": 0.5, "expires_in_hours": 0},
    ]
    monkeypatch.setattr(
        ingestion, "call_qwen_with_functions",
        AsyncMock(return_value=_response(json.dumps({"memories": items}))),
    )
    monkeypatch.setattr(ingestion, "get_embedding", AsyncMock(return_value=[0.1] * 4))
    monkeypatch.setattr(ingestion, "detect_conflicts", AsyncMock(return_value=[]))
    db = _db()

    created = await extract_and_store_memories("text", "u1", "m1", db)

    assert [m.decay_rate for m in created] == [0.0, DECAY_RATES["episodic"], DEFAULT_DECAY_RATE]
    assert created[0].expires_at is None
    assert created[1].expires_at is not None
    db.commit.assert_awaited_once()


async def test_memoryless_and_empty_paths(monkeypatch):
    qwen = AsyncMock(return_value=_response(json.dumps({"memories": []})))
    monkeypatch.setattr(ingestion, "call_qwen_with_functions", qwen)
    assert await extract_and_store_memories("t", "u", "m", _db(), is_memoryless=True) == []
    qwen.assert_not_awaited()
    assert await extract_and_store_memories("t", "u", "m", _db()) == []


async def test_qwen_failure_returns_empty(monkeypatch):
    monkeypatch.setattr(
        ingestion, "call_qwen_with_functions", AsyncMock(side_effect=RuntimeError("x"))
    )
    assert await extract_and_store_memories("t", "u", "m", _db()) == []
