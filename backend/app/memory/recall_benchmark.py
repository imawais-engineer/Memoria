"""Offline recall benchmark: fixed cases scored with any embedding function.

Used by ``scripts/benchmark.py --offline`` (embeddings from the mock
OpenAI-compatible server) and by ``tests/test_recall_benchmark.py``
(deterministic bag-of-words embeddings). No database is needed.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.memory.quality import MemoryRecord, normalize_kind, rank_memories

Embed = Callable[[str], Awaitable[list[float]]]


@dataclass
class SeedMemory:
    key: str
    content: str
    kind: str = "fact"
    type: str = "semantic"
    importance: float = 0.7
    age_days: float = 1.0
    superseded: bool = False


@dataclass
class RecallCase:
    name: str
    query: str
    seeds: list[SeedMemory]
    expected: str  # key of the memory that must rank first
    forbidden: list[str] = field(default_factory=list)  # keys that must not appear


CASES: list[RecallCase] = [
    RecallCase(
        name="diet",
        query="what diet does the user follow vegetarian",
        seeds=[
            SeedMemory("diet", "User follows a vegetarian diet"),
            SeedMemory("hobby", "User enjoys hiking on weekends"),
            SeedMemory("lang", "User is learning the Python language"),
        ],
        expected="diet",
    ),
    RecallCase(
        name="supersede_city",
        query="which city does the user live in",
        seeds=[
            SeedMemory(
                "paris", "User lives in the city of Paris", age_days=90, superseded=True
            ),
            SeedMemory("berlin", "User lives in the city of Berlin", age_days=2),
            SeedMemory("job", "User works as a data engineer"),
        ],
        expected="berlin",
        forbidden=["paris"],
    ),
    RecallCase(
        name="recent_event_beats_stale_event",
        query="what concert did the user attend",
        seeds=[
            SeedMemory(
                "old", "User attended a concert by Radiohead", "event", "episodic",
                age_days=200,
            ),
            SeedMemory(
                "new", "User attended a concert by Beyonce", "event", "episodic",
                age_days=3,
            ),
        ],
        expected="new",
    ),
    RecallCase(
        name="preference",
        query="what food does the user like spicy",
        seeds=[
            SeedMemory("spicy", "User likes spicy food", "preference", "preference"),
            SeedMemory("sleep", "User sleeps eight hours"),
        ],
        expected="spicy",
    ),
]


def bow_embedding(text: str, dim: int = 256) -> list[float]:
    """Deterministic hashed bag-of-words embedding (shared words give similarity)."""

    vec = [0.0] * dim
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        h = int(hashlib.sha256(word.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


async def run_recall_cases(
    embed: Embed,
    cases: list[RecallCase] | None = None,
    *,
    exact_queries: bool = False,
    now: datetime | None = None,
) -> dict:
    """Run all cases. With ``exact_queries`` the query is the expected memory text,
    which suits embeddings that are deterministic but not semantic."""

    now = now or datetime.now(timezone.utc)
    results = []
    for case in cases or CASES:
        records = [
            MemoryRecord(
                id=s.key,
                content=s.content,
                embedding=await embed(s.content),
                importance=s.importance,
                kind=normalize_kind(s.kind, s.type),
                type=s.type,
                created_at=now - timedelta(days=s.age_days),
                superseded=s.superseded,
            )
            for s in case.seeds
        ]
        query = case.query
        if exact_queries:
            query = next(s.content for s in case.seeds if s.key == case.expected)
        ranked = rank_memories(await embed(query), records, now=now, limit=3)
        keys = [rec.id for rec, _ in ranked]
        passed = bool(keys) and keys[0] == case.expected and not (
            set(keys) & set(case.forbidden)
        )
        results.append({"case": case.name, "passed": passed, "ranking": keys})
    passed_n = sum(1 for r in results if r["passed"])
    return {
        "cases": results,
        "passed": passed_n,
        "total": len(results),
        "recall_at_1": passed_n / len(results) if results else 0.0,
    }
