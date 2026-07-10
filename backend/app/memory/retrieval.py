"""Memory retrieval and context packing.

Given a user query, retrieve the most relevant memories (vector similarity
weighted by importance and recency), then greedily pack them into a context
string under a token budget. ``core`` memories are always included first.
"""

from __future__ import annotations

import logging

from sqlalchemy import Float, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dashscope_client import DEFAULT_EMBEDDING_MODEL, get_embedding
from app.memory.models import Memory

logger = logging.getLogger(__name__)

# Number of candidate memories to score in the database before packing.
CANDIDATE_LIMIT = 50

# Fallback token estimate: roughly 4 characters per token.
CHARS_PER_TOKEN = 4

try:  # tiktoken is optional; fall back to a character-based estimate.
    import tiktoken

    _ENCODING = tiktoken.get_encoding("cl100k_base")
except Exception:  # noqa: BLE001
    tiktoken = None  # type: ignore[assignment]
    _ENCODING = None


def count_tokens(text: str) -> int:
    """Count tokens in ``text`` via tiktoken when available, else estimate."""

    if _ENCODING is not None:
        return len(_ENCODING.encode(text))
    return max(1, (len(text) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN)


def _format_memory(memory: Memory) -> str:
    """Render a memory as a context line prefixed with its type and date."""

    created = memory.created_at.strftime("%Y-%m-%d") if memory.created_at else "?"
    return f"[{memory.type} | {created}] {memory.content}"


async def retrieve_context(
    user_id: str,
    query_text: str,
    max_tokens: int = 6000,
    db_session: AsyncSession | None = None,
) -> str:
    """Return a packed context string of the user's most relevant memories.

    Steps:
    1. Embed ``query_text`` with ``text-embedding-v3``.
    2. Select up to :data:`CANDIDATE_LIMIT` non-expired memories for ``user_id``,
       ordered by ``cosine_similarity * importance * recency`` (recency decays
       with each memory's ``decay_rate``; ``core`` memories never decay).
    3. Greedily pack memories into a string until the next would exceed
       ``max_tokens``, always placing ``core`` memories first.
    """

    if db_session is None:
        raise ValueError("db_session is required")

    query_embedding = await get_embedding(query_text, model=DEFAULT_EMBEDDING_MODEL)

    # Similarity in [0, 2] domain: cosine_distance is 1 - cosine_similarity, so
    # similarity = 1 - distance.
    similarity = 1 - Memory.embedding.cosine_distance(query_embedding)

    # Recency factor: exp(-decay_rate * age_in_days). decay_rate=0 (core) -> 1.
    age_days = cast(
        func.extract("epoch", func.now() - Memory.created_at), Float
    ) / 86400.0
    recency = func.exp(-Memory.decay_rate * age_days)

    score = (similarity * Memory.importance * recency).label("score")

    stmt = (
        select(Memory, score)
        .where(Memory.user_id == user_id)
        .where(or_(Memory.expires_at.is_(None), Memory.expires_at > func.now()))
        .order_by(score.desc())
        .limit(CANDIDATE_LIMIT)
    )

    result = await db_session.execute(stmt)
    candidates = [row[0] for row in result.all()]

    if not candidates:
        return ""

    # Core memories first (preserving score order), then the rest.
    core = [m for m in candidates if m.type == "core"]
    non_core = [m for m in candidates if m.type != "core"]

    packed: list[str] = []
    used_tokens = 0

    # Core memories are always included first, regardless of budget.
    for memory in core:
        entry = _format_memory(memory)
        packed.append(entry)
        used_tokens += count_tokens(entry)

    # Greedily add non-core memories until the next one would exceed the budget.
    for memory in non_core:
        entry = _format_memory(memory)
        entry_tokens = count_tokens(entry)
        if used_tokens + entry_tokens > max_tokens:
            break
        packed.append(entry)
        used_tokens += entry_tokens

    logger.info(
        "Packed %d/%d memories (~%d tokens) for user_id=%s",
        len(packed),
        len(candidates),
        used_tokens,
        user_id,
    )
    return "\n".join(packed)
