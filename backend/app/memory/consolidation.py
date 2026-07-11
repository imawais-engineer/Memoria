"""Consolidation engine: cluster similar recent memories and summarize them.

Non-consolidated memories from the past seven days are grouped by pgvector
cosine similarity. Clusters of three or more are summarized by Qwen-Max into a
single semantic memory; originals are linked to the summary via ``parent_id``.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dashscope_client import call_qwen_structured, get_embedding
from app.core.database import async_session
from app.memory.models import Memory

logger = logging.getLogger(__name__)

CONSOLIDATION_MODEL = "qwen-max"
STRUCTURED_FALLBACK_MODEL = "qwen-plus"
SIMILARITY_THRESHOLD = 0.75
MIN_CLUSTER_SIZE = 3
LOOKBACK_DAYS = 7
SUMMARY_IMPORTANCE = 8.0
SUMMARY_DECAY_RATE = 0.01

CONSOLIDATION_SYSTEM_PROMPT = (
    "You are a master memory consolidator. Synthesize these related memories "
    "into ONE concise semantic memory (< 50 words) that captures the essence. "
    "Respond in JSON format."
)

CONSOLIDATION_JSON_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "summary": {
            "type": "string",
            "description": "One concise semantic memory under 50 words.",
        },
        "key_themes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Short theme labels extracted from the cluster.",
        },
    },
    "required": ["summary", "key_themes"],
    "additionalProperties": False,
}


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two equal-length vectors (0 if degenerate)."""

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _cluster_memories(memories: list[Memory]) -> list[list[Memory]]:
    """Greedy clustering by pairwise cosine similarity above the threshold."""

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
                >= SIMILARITY_THRESHOLD
            ):
                cluster.append(memories[j])
                used.add(j)
        clusters.append(cluster)

    return clusters


async def _summarize_cluster(cluster: list[Memory]) -> tuple[str, list[str]] | None:
    """Ask Qwen-Max to synthesize a cluster into structured summary JSON."""

    bullet_points = "\n".join(f"- {memory.content}" for memory in cluster)
    messages = [
        {"role": "system", "content": CONSOLIDATION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Synthesize these memories as JSON:\n{bullet_points}",
        },
    ]
    try:
        for model in (CONSOLIDATION_MODEL, STRUCTURED_FALLBACK_MODEL):
            result = await call_qwen_structured(
                messages,
                CONSOLIDATION_JSON_SCHEMA,
                model=model,
            )
            if isinstance(result.get("summary"), str) and isinstance(
                result.get("key_themes"), list
            ):
                summary = result["summary"].strip()
                key_themes = [str(theme) for theme in result["key_themes"]]
                if summary:
                    return summary, key_themes
            logger.warning(
                "Consolidation structured output missing required fields from %s: %s",
                model,
                result,
            )
        return None
    except Exception:
        logger.warning(
            "Qwen consolidation call failed for cluster of %d memories; skipping",
            len(cluster),
            exc_info=True,
        )
        return None


async def consolidate_memories(user_id: str) -> int:
    """Consolidate non-consolidated memories for ``user_id`` using Qwen-Max clustering.

    Fetches eligible memories from the past seven days, clusters them by
    embedding similarity (>= 0.75), and for each cluster of three or more
    creates a semantic summary memory. Originals are marked consolidated and
    linked to the summary via ``parent_id``.

    Returns the number of summary memories created.
    """

    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    summaries_created = 0
    memories_consolidated = 0

    async with async_session() as db:
        stmt = (
            select(Memory)
            .where(
                Memory.user_id == user_id,
                Memory.is_consolidated.is_(False),
                Memory.archived.is_(False),
                Memory.created_at >= cutoff,
            )
            .order_by(Memory.created_at.asc())
        )
        memories = list((await db.execute(stmt)).scalars().all())
        if len(memories) < MIN_CLUSTER_SIZE:
            logger.info(
                "Consolidated 0 memories for user %s into 0 summaries", user_id
            )
            return 0

        for cluster in _cluster_memories(memories):
            if len(cluster) < MIN_CLUSTER_SIZE:
                continue

            summary_result = await _summarize_cluster(cluster)
            if not summary_result:
                continue

            summary_text, key_themes = summary_result

            try:
                embedding = await get_embedding(summary_text)
            except Exception:
                logger.warning(
                    "Embedding failed for consolidation summary; skipping cluster",
                    exc_info=True,
                )
                continue

            summary = Memory(
                user_id=user_id,
                type="semantic",
                content=summary_text,
                embedding=embedding,
                importance=SUMMARY_IMPORTANCE,
                decay_rate=SUMMARY_DECAY_RATE,
                meta_data={
                    "source": "consolidation",
                    "key_themes": key_themes,
                    "consolidated_from": [str(memory.id) for memory in cluster],
                },
            )
            db.add(summary)
            await db.flush()

            now = datetime.now(timezone.utc)
            for memory in cluster:
                memory.parent_id = summary.id
                memory.is_consolidated = True
                memory.consolidated_at = now

            summaries_created += 1
            memories_consolidated += len(cluster)

        if summaries_created:
            await db.commit()
        else:
            await db.rollback()

    logger.info(
        "Consolidated %d memories for user %s into %d summaries",
        memories_consolidated,
        user_id,
        summaries_created,
    )
    return summaries_created


async def get_consolidation_stats(user_id: str) -> dict[str, int]:
    """Return consolidation statistics for ``user_id``."""

    async with async_session() as db:
        total_stmt = select(func.count()).select_from(Memory).where(
            Memory.user_id == user_id,
            Memory.archived.is_(False),
        )
        consolidated_stmt = select(func.count()).select_from(Memory).where(
            Memory.user_id == user_id,
            Memory.is_consolidated.is_(True),
        )
        summaries_stmt = select(func.count()).select_from(Memory).where(
            Memory.user_id == user_id,
            Memory.meta_data["source"].astext == "consolidation",
        )

        total_memories = (await db.execute(total_stmt)).scalar_one()
        consolidated_count = (await db.execute(consolidated_stmt)).scalar_one()
        summaries = (await db.execute(summaries_stmt)).scalar_one()

    return {
        "total_memories": total_memories,
        "consolidated_count": consolidated_count,
        "summaries": summaries,
    }


async def fetch_active_user_ids(lookback_days: int = LOOKBACK_DAYS) -> list[str]:
    """Return user IDs with non-consolidated memories in the lookback window."""

    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    async with async_session() as db:
        stmt = (
            select(Memory.user_id)
            .where(
                Memory.is_consolidated.is_(False),
                Memory.archived.is_(False),
                Memory.created_at >= cutoff,
            )
            .distinct()
        )
        return [row[0] for row in (await db.execute(stmt)).all()]
