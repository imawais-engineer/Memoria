"""DB-less tests for retrieval token counting and context packing."""

from datetime import datetime, timezone
from types import SimpleNamespace

from app.memory import retrieval
from app.memory.retrieval import _format_memory, _pack_memories, count_tokens


def _mem(type_, content, day=1):
    return SimpleNamespace(
        type=type_,
        content=content,
        created_at=datetime(2025, 1, day, tzinfo=timezone.utc),
        id=f"{type_}-{content}",
    )


def test_count_tokens_positive_and_monotonic():
    assert count_tokens("hello") >= 1
    assert count_tokens("hello world " * 50) > count_tokens("hello world")


def test_count_tokens_fallback_estimate(monkeypatch):
    monkeypatch.setattr(retrieval, "_ENCODING", None)
    assert count_tokens("a" * 8) == 2
    assert count_tokens("") == 1


def test_format_memory():
    assert _format_memory(_mem("goal", "run a marathon", 5)) == (
        "[goal | 2025-01-05] run a marathon"
    )
    m = _mem("goal", "x")
    m.created_at = None
    assert _format_memory(m) == "[goal | ?] x"


def test_core_first_ordering():
    items = [_mem("episodic", "a"), _mem("core", "b"), _mem("semantic", "c")]
    entries, mems, _ = _pack_memories(items, 10_000)
    assert [m.type for m in mems] == ["core", "episodic", "semantic"]
    assert entries[0].startswith("[core")


def test_budget_stops_packing_but_keeps_core():
    core = _mem("core", "must keep " * 20)
    others = [_mem("semantic", f"fact {i} " * 10) for i in range(5)]
    budget = count_tokens(_format_memory(core)) + count_tokens(
        _format_memory(others[0])
    )
    _, mems, used = _pack_memories([others[0], core, *others[1:]], budget)
    assert mems == [core, others[0]]
    assert used <= budget

    # Core is included even when it alone exceeds the budget.
    _, mems, _ = _pack_memories([others[0], core], 1)
    assert mems == [core]


def test_empty_candidates():
    assert _pack_memories([], 100) == ([], [], 0)
