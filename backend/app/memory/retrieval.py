"""Memory retrieval and context packing.

Given a user query, retrieve the most relevant memories (vector similarity
weighted by importance and recency), then greedily pack them into a context
string under a token budget. ``core`` memories are always included first.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import Float, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dashscope_client import DEFAULT_EMBEDDING_MODEL, get_embedding
from app.memory.models import Memory
from app.memory.quality import build_why

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


def _pack_memories(
    candidates: list[Memory], max_tokens: int
) -> tuple[list[str], list[Memory], int]:
    """Greedily pack memories under ``max_tokens``, core memories first.

    Core memories are always included (even past the budget); other memories
    are added in order until the next one would exceed the budget.
    Returns ``(entries, memories, used_tokens)``.
    """

    core = [m for m in candidates if m.type == "core"]
    non_core = [m for m in candidates if m.type != "core"]

    entries: list[str] = []
    memories: list[Memory] = []
    used_tokens = 0

    for memory in core:
        entry = _format_memory(memory)
        entries.append(entry)
        memories.append(memory)
        used_tokens += count_tokens(entry)

    for memory in non_core:
        entry = _format_memory(memory)
        entry_tokens = count_tokens(entry)
        if used_tokens + entry_tokens > max_tokens:
            break
        entries.append(entry)
        memories.append(memory)
        used_tokens += entry_tokens

    return entries, memories, used_tokens


async def _fetch_scored(
    user_id: str,
    query_text: str,
    db_session: AsyncSession,
    *,
    session_id: str | None,
    is_memoryless: bool,
    global_memory_enabled: bool,
    include_superseded: bool = False,
) -> list[tuple[Memory, float]]:
    """Return ``(memory, similarity)`` pairs ordered by recall score."""

    if is_memoryless:
        return []

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
        or_(Memory.expires_at.is_(None), Memory.expires_at > func.now()),
    ]
    if not include_superseded:
        filters.append(Memory.superseded.is_(False))

    if not global_memory_enabled:
        # Personal Intelligence OFF: current-session memories plus manually
        # memorized core facts (no session binding).
        if session_id:
            try:
                session_uuid = uuid.UUID(session_id)
            except ValueError:
                return []
            filters.append(
                or_(
                    Memory.session_id == session_uuid,
                    (Memory.type == "core") & Memory.session_id.is_(None),
                )
            )
        else:
            filters.append(
                (Memory.type == "core") & Memory.session_id.is_(None)
            )

    stmt = (
        select(Memory, similarity.label("similarity"))
        .where(*filters)
        .order_by(score.desc())
        .limit(CANDIDATE_LIMIT)
    )

    result = await db_session.execute(stmt)
    return [(row[0], float(row[1] or 0.0)) for row in result.all()]


def explain_memory(memory: Memory, similarity: float, now: datetime | None = None) -> dict:
    """Build the ``why`` dict (similarity, recency, importance, kind) for a memory."""

    now = now or datetime.now(timezone.utc)
    created = memory.created_at or now
    age_days = max((now - created).total_seconds(), 0.0) / 86400.0
    return build_why(
        similarity,
        memory.importance if memory.importance is not None else 0.5,
        memory.decay_rate or 0.0,
        age_days,
        memory.kind,
        memory.type,
    ).as_dict()


async def retrieve_with_why(
    user_id: str,
    query_text: str,
    max_tokens: int = 6000,
    db_session: AsyncSession | None = None,
    *,
    session_id: str | None = None,
    is_memoryless: bool = False,
    global_memory_enabled: bool = True,
    include_superseded: bool = False,
) -> list[dict]:
    """Return recalled memories, each with a ``why`` explanation.

    Superseded memories are excluded unless ``include_superseded`` is true.
    """

    if db_session is None:
        raise ValueError("db_session is required")

    pairs = await _fetch_scored(
        user_id,
        query_text,
        db_session,
        session_id=session_id,
        is_memoryless=is_memoryless,
        global_memory_enabled=global_memory_enabled,
        include_superseded=include_superseded,
    )
    sims = {m.id: s for m, s in pairs}
    _, packed, _ = _pack_memories([m for m, _ in pairs], max_tokens)
    return [
        {
            "id": str(m.id),
            "type": m.type,
            "kind": m.kind,
            "content": m.content,
            "superseded": bool(m.superseded),
            "why": explain_memory(m, sims[m.id]),
        }
        for m in packed
    ]


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

    pairs = await _fetch_scored(
        user_id,
        query_text,
        db_session,
        session_id=session_id,
        is_memoryless=is_memoryless,
        global_memory_enabled=global_memory_enabled,
    )
    candidates = [m for m, _ in pairs]

    if not candidates:
        return "", []

    packed_entries, packed_memories, used_tokens = _pack_memories(
        candidates, max_tokens
    )

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
