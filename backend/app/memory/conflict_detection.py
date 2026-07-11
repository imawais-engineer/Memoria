"""Memory conflict detection and versioning.

Detects semantically similar memories that contradict each other using pgvector
similarity and Qwen-Plus judgment, then versions older facts via supersession.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dashscope_client import call_qwen_structured, get_embedding
from app.memory.models import Memory

logger = logging.getLogger(__name__)

CONTRADICTION_MODEL = "qwen-plus"
SIMILARITY_THRESHOLD = 0.7
SIMILAR_CANDIDATE_LIMIT = 20

CONTRADICTION_SYSTEM_PROMPT = (
    "You are a fact-checker for a personal memory system. Determine whether two "
    "statements about the same user are factually contradictory—they cannot both "
    "be true at the same time. Examples of contradictions: 'allergic to peanuts' "
    "vs 'loves peanut butter', 'vegetarian' vs 'eats steak every week'. "
    "Respond in JSON format."
)

CONTRADICTION_JSON_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "contradiction": {
            "type": "boolean",
            "description": "True when the statements cannot both be true.",
        },
        "reason": {
            "type": "string",
            "description": "Brief explanation of the judgment.",
        },
    },
    "required": ["contradiction", "reason"],
    "additionalProperties": False,
}


async def _is_contradiction(existing_content: str, new_content: str) -> bool:
    """Ask Qwen-Plus whether two memory statements contradict each other."""

    messages = [
        {"role": "system", "content": CONTRADICTION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Statement A: {existing_content}\n"
                f"Statement B: {new_content}\n\n"
                "Return JSON indicating whether these contradict."
            ),
        },
    ]
    try:
        result = await call_qwen_structured(
            messages, CONTRADICTION_JSON_SCHEMA, model=CONTRADICTION_MODEL
        )
        if not isinstance(result.get("contradiction"), bool) or not isinstance(
            result.get("reason"), str
        ):
            logger.warning(
                "Contradiction structured output missing required fields: %s",
                result,
            )
            return False
        contradiction = result["contradiction"]
        if contradiction:
            logger.info("Structured contradiction check: %s", result["reason"])
        return contradiction
    except Exception:
        logger.warning(
            "Contradiction check failed; treating as non-conflicting",
            exc_info=True,
        )
        return False


async def detect_conflicts(
    db_session: AsyncSession,
    user_id: str,
    new_memory_content: str,
    *,
    exclude_memory_id: uuid.UUID | None = None,
) -> list[Memory]:
    """Find existing memories that contradict ``new_memory_content``.

    Uses pgvector cosine similarity (> 0.7) to surface semantically similar
    memories, then asks Qwen-Plus to judge factual contradiction for each
    candidate. Returns conflicting :class:`Memory` rows (may be empty).
    """

    if not new_memory_content.strip():
        return []

    try:
        query_embedding = await get_embedding(new_memory_content)
    except Exception:
        logger.warning(
            "Failed to embed new memory for conflict detection", exc_info=True
        )
        return []

    max_distance = 1.0 - SIMILARITY_THRESHOLD
    stmt = (
        select(Memory)
        .where(
            Memory.user_id == user_id,
            Memory.archived.is_(False),
            Memory.superseded.is_(False),
            Memory.embedding.cosine_distance(query_embedding) < max_distance,
        )
        .order_by(Memory.embedding.cosine_distance(query_embedding))
        .limit(SIMILAR_CANDIDATE_LIMIT)
    )
    if exclude_memory_id is not None:
        stmt = stmt.where(Memory.id != exclude_memory_id)

    candidates = list((await db_session.execute(stmt)).scalars().all())
    if not candidates:
        return []

    conflicts: list[Memory] = []
    for candidate in candidates:
        if await _is_contradiction(candidate.content, new_memory_content):
            conflicts.append(candidate)
            logger.info(
                "Contradiction detected between new content and memory_id=%s",
                candidate.id,
            )

    return conflicts


async def resolve_conflict(
    db_session: AsyncSession,
    old_memory_id: str,
    new_memory_id: str,
    resolution: str,
) -> bool:
    """Mark ``old_memory_id`` as superseded by ``new_memory_id``.

    Sets ``superseded=True``, ``superseded_by``, and records
    ``metadata.conflict_resolution``. Returns ``True`` on success.
    """

    try:
        old_uuid = uuid.UUID(old_memory_id)
        new_uuid = uuid.UUID(new_memory_id)
    except (ValueError, AttributeError, TypeError):
        logger.warning(
            "resolve_conflict: invalid memory id old=%s new=%s",
            old_memory_id,
            new_memory_id,
        )
        return False

    try:
        old_memory = await db_session.get(Memory, old_uuid)
        if old_memory is None:
            return False
        new_memory = await db_session.get(Memory, new_uuid)
        if new_memory is None:
            return False

        meta = dict(old_memory.meta_data or {})
        meta["conflict_resolution"] = resolution
        old_memory.meta_data = meta
        old_memory.superseded = True
        old_memory.superseded_by = new_uuid
        await db_session.flush()
        return True
    except Exception:
        logger.exception(
            "resolve_conflict failed old=%s new=%s", old_memory_id, new_memory_id
        )
        return False
