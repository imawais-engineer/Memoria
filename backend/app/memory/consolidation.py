"""Consolidation engine: cluster similar recent memories and summarize them.

Weekly, for each user, recent ``episodic``/``semantic`` memories are clustered
by pairwise cosine similarity. Any cluster with more than
:data:`MIN_CLUSTER_SIZE` memories is summarized by Qwen-Max into a single new
``semantic`` memory, and the originals are archived (soft-deleted).
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dashscope_client import call_qwen_chat, get_embedding
from app.memory.models import Memory

logger = logging.getLogger(__name__)

# Model used to generate cluster summaries (per roadmap Module 5).
CONSOLIDATION_MODEL = "qwen-max"

# Cosine similarity above which two memories are considered part of a cluster.
SIMILARITY_THRESHOLD = 0.8

# Only clusters with strictly more than this many memories are consolidated.
MIN_CLUSTER_SIZE = 3

# Lookback window for memories eligible for consolidation.
LOOKBACK_DAYS = 7

# Decay rate assigned to a consolidated (semantic) summary memory.
SEMANTIC_DECAY_RATE = 0.01


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two equal-length vectors (0 if degenerate)."""

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _cluster_memories(memories: list[Memory]) -> list[list[Memory]]:
    """Greedy single-pass clustering by pairwise cosine similarity.

    Each unassigned memory seeds a cluster and absorbs any remaining memory
    whose similarity to the seed exceeds :data:`SIMILARITY_THRESHOLD`.
    """

    clusters: list[list[Memory]] = []
    used: set[int] = set()

    for i, seed in enumerate(memories):
        if i in used:
            continue
        cluster = [seed]
        used.add(i)
        seed_vec = list(seed.embedding)
        for j in range(i + 1, len(memories)):
            if j in used:
                continue
            if (
                _cosine_similarity(seed_vec, list(memories[j].embedding))
                > SIMILARITY_THRESHOLD
            ):
                cluster.append(memories[j])
                used.add(j)
        clusters.append(cluster)

    return clusters


async def _summarize_cluster(cluster: list[Memory]) -> str:
    """Ask Qwen-Max to summarize a cluster of memories into one statement."""

    bullet_points = "\n".join(f"- {m.content}" for m in cluster)
    messages = [
        {
            "role": "system",
            "content": (
                "You consolidate related memories about a user into a single, "
                "concise factual summary. Respond with only the summary text."
            ),
        },
        {
            "role": "user",
            "content": f"Summarize these related memories into one memory:\n{bullet_points}",
        },
    ]
    return (await call_qwen_chat(messages, model=CONSOLIDATION_MODEL)).strip()


async def consolidate_memories(db_session: AsyncSession) -> dict[str, int]:
    """Cluster and summarize recent memories per user.

    Returns a summary dict with the number of clusters consolidated and the
    number of original memories archived. Commits via the provided session.
    """

    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)

    users_stmt = (
        select(Memory.user_id)
        .where(
            Memory.type.in_(["episodic", "semantic"]),
            Memory.created_at >= cutoff,
            Memory.archived.is_(False),
        )
        .distinct()
    )
    user_ids = [row[0] for row in (await db_session.execute(users_stmt)).all()]

    clusters_consolidated = 0
    memories_archived = 0

    for user_id in user_ids:
        mem_stmt = (
            select(Memory)
            .where(
                Memory.user_id == user_id,
                Memory.type.in_(["episodic", "semantic"]),
                Memory.created_at >= cutoff,
                Memory.archived.is_(False),
            )
            .order_by(Memory.created_at.asc())
        )
        memories = list((await db_session.execute(mem_stmt)).scalars().all())
        if len(memories) <= MIN_CLUSTER_SIZE:
            continue

        for cluster in _cluster_memories(memories):
            if len(cluster) <= MIN_CLUSTER_SIZE:
                continue

            summary_text = await _summarize_cluster(cluster)
            if not summary_text:
                continue

            avg_importance = sum(m.importance for m in cluster) / len(cluster)
            oldest = min(cluster, key=lambda m: m.created_at)
            embedding = await get_embedding(summary_text)

            summary = Memory(
                user_id=user_id,
                type="semantic",
                content=summary_text,
                embedding=embedding,
                importance=avg_importance,
                decay_rate=SEMANTIC_DECAY_RATE,
                parent_id=oldest.id,
                meta_data={
                    "consolidated_from": [str(m.id) for m in cluster],
                },
            )
            db_session.add(summary)

            for memory in cluster:
                memory.archived = True

            clusters_consolidated += 1
            memories_archived += len(cluster)

    await db_session.commit()

    summary_stats = {
        "clusters_consolidated": clusters_consolidated,
        "memories_archived": memories_archived,
    }
    logger.info(
        "consolidate_memories: clusters=%d archived=%d",
        clusters_consolidated,
        memories_archived,
    )
    return summary_stats
