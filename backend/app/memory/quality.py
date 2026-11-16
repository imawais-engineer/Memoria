"""Pure memory-quality logic: kinds, decay rates, supersede and explanations.

Nothing here touches the database or the network, so it is unit-testable
offline. The DB-facing modules (ingestion, retrieval, forgetting) call into it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.config import get_settings

KINDS: tuple[str, ...] = ("fact", "event", "preference")
DEFAULT_KIND = "fact"

# Legacy ``type`` values mapped to the closest kind (used by the migration too).
_TYPE_TO_KIND: dict[str, str] = {
    "episodic": "event",
    "preference": "preference",
}


def normalize_kind(kind: str | None, mem_type: str | None = None) -> str:
    """Return a valid kind, deriving it from ``mem_type`` when ``kind`` is unset."""

    if kind in KINDS:
        return str(kind)
    return _TYPE_TO_KIND.get(mem_type or "", DEFAULT_KIND)


def kind_decay_rates() -> dict[str, float]:
    """Per-day decay rate for each kind, read from settings."""

    settings = get_settings()
    return {
        "fact": settings.decay_rate_fact,
        "event": settings.decay_rate_event,
        "preference": settings.decay_rate_preference,
    }


def decay_rate_for(kind: str | None, mem_type: str | None = None) -> float:
    """Decay rate for a memory. ``core`` memories never decay."""

    if mem_type == "core":
        return 0.0
    return kind_decay_rates()[normalize_kind(kind, mem_type)]


def decide_supersede(
    old_created_at: datetime | None,
    new_created_at: datetime | None,
    *,
    contradicts: bool,
    old_kind: str = DEFAULT_KIND,
    new_kind: str = DEFAULT_KIND,
) -> bool:
    """Whether the new memory should supersede the old one.

    Only contradicting facts and preferences are superseded, and only when the
    new memory is not older than the existing one. Events are history: two
    events can both have happened, so they are never superseded.
    """

    if not contradicts:
        return False
    if "event" in (old_kind, new_kind):
        return False
    if old_created_at and new_created_at and new_created_at < old_created_at:
        return False
    return True


@dataclass(frozen=True)
class Why:
    """Explanation of why a memory was recalled."""

    similarity: float
    recency: float
    importance: float
    kind: str
    score: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "similarity": round(self.similarity, 4),
            "recency": round(self.recency, 4),
            "importance": round(self.importance, 4),
            "kind": self.kind,
            "score": round(self.score, 4),
            "summary": self.summary(),
        }

    def summary(self) -> str:
        return (
            f"{self.kind}: similarity {self.similarity:.2f}, "
            f"recency {self.recency:.2f}, importance {self.importance:.2f}"
        )


def recency_factor(decay_rate: float, age_days: float) -> float:
    return math.exp(-decay_rate * max(age_days, 0.0))


def build_why(
    similarity: float,
    importance: float,
    decay_rate: float,
    age_days: float,
    kind: str | None,
    mem_type: str | None = None,
) -> Why:
    """Build the score breakdown (score = similarity * importance * recency)."""

    recency = recency_factor(decay_rate, age_days)
    return Why(
        similarity=similarity,
        recency=recency,
        importance=importance,
        kind=normalize_kind(kind, mem_type),
        score=similarity * importance * recency,
    )


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


@dataclass
class MemoryRecord:
    """In-memory stand-in for a Memory row, used by the offline recall logic."""

    id: str
    content: str
    embedding: list[float]
    importance: float = 0.5
    kind: str = DEFAULT_KIND
    type: str = "semantic"
    created_at: datetime | None = None
    superseded: bool = False
    archived: bool = False
    decay_rate: float | None = None


def rank_memories(
    query_embedding: list[float],
    records: list[MemoryRecord],
    *,
    now: datetime | None = None,
    include_superseded: bool = False,
    limit: int = 5,
) -> list[tuple[MemoryRecord, Why]]:
    """Rank records like the SQL in ``retrieval`` and attach ``Why`` data."""

    now = now or datetime.now(timezone.utc)
    ranked: list[tuple[MemoryRecord, Why]] = []
    for rec in records:
        if rec.archived or (rec.superseded and not include_superseded):
            continue
        rate = rec.decay_rate
        if rate is None:
            rate = decay_rate_for(rec.kind, rec.type)
        age = (now - rec.created_at).total_seconds() / 86400.0 if rec.created_at else 0.0
        why = build_why(
            cosine(query_embedding, rec.embedding),
            rec.importance,
            rate,
            age,
            rec.kind,
            rec.type,
        )
        ranked.append((rec, why))
    ranked.sort(key=lambda pair: pair[1].score, reverse=True)
    return ranked[:limit]
