"""Pure-logic tests for memory kinds, decay, supersede and why explanations."""

from datetime import datetime, timedelta, timezone

from app.memory.forgetting import decayed_importance_for_kind
from app.memory.quality import (
    MemoryRecord,
    build_why,
    decay_rate_for,
    decide_supersede,
    normalize_kind,
    rank_memories,
)


def test_normalize_kind_defaults_and_legacy_types():
    assert normalize_kind("preference") == "preference"
    assert normalize_kind(None, "episodic") == "event"
    assert normalize_kind("bogus", "semantic") == "fact"
    assert normalize_kind(None) == "fact"


def test_decay_by_kind_ordering_and_core():
    assert decay_rate_for("event") > decay_rate_for("preference") > decay_rate_for("fact")
    assert decay_rate_for("event", "core") == 0.0
    fact = decayed_importance_for_kind(1.0, "fact", 30)
    event = decayed_importance_for_kind(1.0, "event", 30)
    assert event < fact < 1.0
    assert decayed_importance_for_kind(1.0, "event", 30, "core") == 1.0


def test_supersede_decision():
    old = datetime(2024, 1, 1, tzinfo=timezone.utc)
    new = datetime(2024, 6, 1, tzinfo=timezone.utc)
    assert decide_supersede(old, new, contradicts=True)
    assert not decide_supersede(old, new, contradicts=False)
    assert not decide_supersede(new, old, contradicts=True)  # new one is older
    assert not decide_supersede(old, new, contradicts=True, new_kind="event")
    assert decide_supersede(old, new, contradicts=True, old_kind="preference")


def test_why_breakdown():
    why = build_why(0.8, 0.5, 0.0, 100, "preference")
    assert why.score == 0.8 * 0.5 * 1.0
    d = why.as_dict()
    assert set(d) >= {"similarity", "recency", "importance", "kind", "summary"}
    assert d["kind"] == "preference"
    assert build_why(0.8, 0.5, 0.03, 100, "event").recency < 0.1


def test_rank_excludes_superseded_by_default_and_includes_on_request():
    now = datetime.now(timezone.utc)
    v = [1.0, 0.0]
    old = MemoryRecord("old", "a", v, superseded=True, created_at=now - timedelta(days=9))
    new = MemoryRecord("new", "b", v, created_at=now)
    assert [r.id for r, _ in rank_memories(v, [old, new], now=now)] == ["new"]
    ids = [r.id for r, _ in rank_memories(v, [old, new], now=now, include_superseded=True)]
    assert set(ids) == {"old", "new"}
