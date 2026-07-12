"""Memory retrieval and context packing.

Given a user query, retrieve the most relevant memories (vector similarity
weighted by importance and recency), then greedily pack them into a context
string under a token budget. ``core`` memories are always included first.
"""

from __future__ import annotations

import logging
import uuid

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


async def retrieve_context_and_ids(
    user_id: str,
    query_text: str,
    max_tokens: int = 6000,
    db_session: AsyncSession | None = None,
    *,
    session_id: str | None = None,
    is_memoryless: bool = False,
    global_memory_enabled: bool = True,
) -> tuple[str, list[str]]:
    """Return packed context text and the IDs of memories included in it."""

    if db_session is None:
        raise ValueError("db_session is required")

    if is_memoryless:
        return "", []

    query_embedding = await get_embedding(query_text, model=DEFAULT_EMBEDDING_MODEL)

    similarity = 1 - Memory.embedding.cosine_distance(query_embedding)

    age_days = cast(
        func.extract("epoch", func.now() - Memory.created_at), Float
    ) / 86400.0
    recency = func.exp(-Memory.decay_rate * age_days)

    score = (similarity * Memory.importance * recency).label("score")

    filters = [
        Memory.user_id == user_id,
        Memory.archived.is_(False),
        Memory.superseded.is_(False),
        or_(Memory.expires_at.is_(None), Memory.expires_at > func.now()),
    ]

    if not global_memory_enabled:
        scope_filters = [Memory.type == "core"]
        if session_id:
            try:
                session_uuid = uuid.UUID(session_id)
                scope_filters.append(Memory.session_id == session_uuid)
            except ValueError:
                pass
        filters.append(or_(*scope_filters))

    stmt = (
        select(Memory, score)
        .where(*filters)
        .order_by(score.desc())
        .limit(CANDIDATE_LIMIT)
    )

    result = await db_session.execute(stmt)
    candidates = [row[0] for row in result.all()]

    if not candidates:
        return "", []

    core = [m for m in candidates if m.type == "core"]
    non_core = [m for m in candidates if m.type != "core"]

    packed_entries: list[str] = []
    packed_memories: list[Memory] = []
    used_tokens = 0

    for memory in core:
        entry = _format_memory(memory)
        packed_entries.append(entry)
        packed_memories.append(memory)
        used_tokens += count_tokens(entry)

    for memory in non_core:
        entry = _format_memory(memory)
        entry_tokens = count_tokens(entry)
        if used_tokens + entry_tokens > max_tokens:
            break
        packed_entries.append(entry)
        packed_memories.append(memory)
        used_tokens += entry_tokens

    logger.info(
        "Packed %d/%d memories (~%d tokens) for user_id=%s",
        len(packed_memories),
        len(candidates),
        used_tokens,
        user_id,
    )
    return "\n".join(packed_entries), [str(memory.id) for memory in packed_memories]


async def retrieve_context(
    user_id: str,
    query_text: str,
    max_tokens: int = 6000,
    db_session: AsyncSession | None = None,
    *,
    session_id: str | None = None,
    is_memoryless: bool = False,
    global_memory_enabled: bool = True,
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

    context, _ = await retrieve_context_and_ids(
        user_id,
        query_text,
        max_tokens=max_tokens,
        db_session=db_session,
        session_id=session_id,
        is_memoryless=is_memoryless,
        global_memory_enabled=global_memory_enabled,
    )
    return context
