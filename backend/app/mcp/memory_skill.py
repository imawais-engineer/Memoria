"""MCP memory skill tools for Qwen function calling.

Async tool implementations backed by the existing ``Memory`` model and async
SQLAlchemy session. Each tool verifies ``user_id`` ownership before mutating
data.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.models import Memory

logger = logging.getLogger(__name__)

CORE_MEMORY_IMPORTANCE_THRESHOLD = 7.0
PREFERENCE_IMPORTANCE_THRESHOLD = 8.0
MAX_IMPORTANCE = 10.0
CORE_MEMORY_LOOKBACK_DAYS = 30

EMPTY_PREFERENCES: dict[str, list[str]] = {
    "allergies": [],
    "interests": [],
    "goals": [],
    "constraints": [],
}

# Qwen-compatible MCP tool catalog (OpenAI-style function definitions).
MEMORY_TOOL_CATALOG: list[dict[str, Any]] = [
    {
        "name": "get_core_memories",
        "description": "Retrieve important memories for a user (importance >= 7)",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "Owner of the memories to retrieve.",
                }
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "get_user_preferences",
        "description": "Extract user preferences from memories",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "Owner whose preferences should be extracted.",
                }
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "forget_memory",
        "description": "Soft-delete a memory with reason",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "Owner of the memory.",
                },
                "memory_id": {
                    "type": "string",
                    "description": "UUID of the memory to forget.",
                },
                "reason": {
                    "type": "string",
                    "description": "Why the memory is being removed.",
                },
            },
            "required": ["user_id", "memory_id", "reason"],
        },
    },
    {
        "name": "strengthen_memory",
        "description": "Increase importance of a memory (capped at 10)",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "Owner of the memory.",
                },
                "memory_id": {
                    "type": "string",
                    "description": "UUID of the memory to strengthen.",
                },
            },
            "required": ["user_id", "memory_id"],
        },
    },
]

_ALLERGY_PATTERN = re.compile(
    r"\b(allerg(?:y|ies)|intoleran(?:t|ce)|cannot eat|can't eat|avoid)\b",
    re.IGNORECASE,
)
_INTEREST_PATTERN = re.compile(
    r"\b(interest(?:ed)? in|enjoys?|likes?|loves?|passion(?:ate)? about|hobby|hobbies)\b",
    re.IGNORECASE,
)
_GOAL_PATTERN = re.compile(
    r"\b(goal|want(?:s)? to|plan(?:s)? to|aim(?:s)? to|hoping to|trying to)\b",
    re.IGNORECASE,
)
_CONSTRAINT_PATTERN = re.compile(
    r"\b(constraint|must not|cannot|can't|avoid|restriction|limited to|only)\b",
    re.IGNORECASE,
)


def _parse_uuid(memory_id: str) -> uuid.UUID | None:
    """Return a UUID object or ``None`` when ``memory_id`` is invalid."""

    try:
        return uuid.UUID(memory_id)
    except (ValueError, AttributeError, TypeError):
        return None


def _extract_preferences_from_content(content: str) -> dict[str, list[str]]:
    """Heuristically bucket a memory line into preference categories."""

    buckets: dict[str, list[str]] = {
        "allergies": [],
        "interests": [],
        "goals": [],
        "constraints": [],
    }
    text = content.strip()
    if not text:
        return buckets

    if _ALLERGY_PATTERN.search(text):
        buckets["allergies"].append(text)
    if _INTEREST_PATTERN.search(text):
        buckets["interests"].append(text)
    if _GOAL_PATTERN.search(text):
        buckets["goals"].append(text)
    if _CONSTRAINT_PATTERN.search(text):
        buckets["constraints"].append(text)
    return buckets


def _merge_preferences(
    base: dict[str, list[str]], extra: dict[str, list[str]]
) -> dict[str, list[str]]:
    """Merge preference lists while deduplicating entries."""

    merged = {key: list(base[key]) for key in base}
    for key, values in extra.items():
        for value in values:
            if value not in merged[key]:
                merged[key].append(value)
    return merged


def _preferences_from_meta(meta: dict[str, Any]) -> dict[str, list[str]] | None:
    """Read structured preferences from memory metadata when present."""

    if not meta:
        return None

    structured = meta.get("preferences")
    if isinstance(structured, dict):
        return {
            "allergies": list(structured.get("allergies") or []),
            "interests": list(structured.get("interests") or []),
            "goals": list(structured.get("goals") or []),
            "constraints": list(structured.get("constraints") or []),
        }
    return None


async def get_core_memories(user_id: str, db: AsyncSession) -> list[dict[str, Any]]:
    """Return high-importance recent memories for ``user_id``.

    Selects active (non-archived) memories with ``importance >= 7`` created in
    the last 30 days. Returns an empty list when the user has none or on read
    errors.
    """

    if not user_id:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=CORE_MEMORY_LOOKBACK_DAYS)

    try:
        stmt = (
            select(Memory)
            .where(
                Memory.user_id == user_id,
                Memory.archived.is_(False),
                Memory.importance >= CORE_MEMORY_IMPORTANCE_THRESHOLD,
                Memory.created_at >= cutoff,
            )
            .order_by(Memory.importance.desc(), Memory.created_at.desc())
        )
        rows = (await db.execute(stmt)).scalars().all()
        return [
            {
                "id": str(memory.id),
                "content": memory.content,
                "importance": int(memory.importance),
                "created_at": memory.created_at.isoformat() if memory.created_at else "",
            }
            for memory in rows
        ]
    except Exception:
        logger.exception("get_core_memories failed for user_id=%s", user_id)
        return []


async def get_user_preferences(user_id: str, db: AsyncSession) -> dict[str, list[str]]:
    """Extract preference buckets from the user's strongest memories.

    Reads structured ``metadata.preferences`` when available, otherwise applies
    lightweight keyword heuristics to memory content. Returns an empty structure
    when no qualifying memories exist.
    """

    if not user_id:
        return dict(EMPTY_PREFERENCES)

    try:
        stmt = (
            select(Memory)
            .where(
                Memory.user_id == user_id,
                Memory.archived.is_(False),
                Memory.importance >= PREFERENCE_IMPORTANCE_THRESHOLD,
            )
            .order_by(Memory.importance.desc(), Memory.created_at.desc())
        )
        rows = (await db.execute(stmt)).scalars().all()
        if not rows:
            return dict(EMPTY_PREFERENCES)

        preferences = dict(EMPTY_PREFERENCES)
        for memory in rows:
            structured = _preferences_from_meta(memory.meta_data)
            if structured:
                preferences = _merge_preferences(preferences, structured)
            else:
                preferences = _merge_preferences(
                    preferences, _extract_preferences_from_content(memory.content)
                )
        return preferences
    except Exception:
        logger.exception("get_user_preferences failed for user_id=%s", user_id)
        return dict(EMPTY_PREFERENCES)


async def forget_memory(
    user_id: str, memory_id: str, reason: str, db: AsyncSession
) -> bool:
    """Soft-delete a memory after verifying ownership.

    Marks the row as archived and records the deletion reason in metadata.
    Returns ``True`` on success and ``False`` when the memory is missing,
    unauthorized, or the operation fails.
    """

    if not user_id or not memory_id:
        return False

    mem_uuid = _parse_uuid(memory_id)
    if mem_uuid is None:
        logger.warning("forget_memory: invalid memory_id=%s", memory_id)
        return False

    try:
        memory = await db.get(Memory, mem_uuid)
        if memory is None or memory.archived:
            return False
        if memory.user_id != user_id:
            logger.warning(
                "forget_memory: ownership mismatch user_id=%s memory_id=%s",
                user_id,
                memory_id,
            )
            return False

        meta = dict(memory.meta_data or {})
        meta["delete_reason"] = reason
        meta["deleted_at"] = datetime.now(timezone.utc).isoformat()
        memory.meta_data = meta
        memory.archived = True
        await db.commit()
        return True
    except Exception:
        logger.exception(
            "forget_memory failed for user_id=%s memory_id=%s", user_id, memory_id
        )
        await db.rollback()
        return False


async def strengthen_memory(user_id: str, memory_id: str, db: AsyncSession) -> bool:
    """Increase a memory's importance by 1, capped at 10.

    Updates ``last_accessed`` to reflect the reinforcement. Returns ``True`` on
    success and ``False`` when the memory is missing, unauthorized, or the
    operation fails.
    """

    if not user_id or not memory_id:
        return False

    mem_uuid = _parse_uuid(memory_id)
    if mem_uuid is None:
        logger.warning("strengthen_memory: invalid memory_id=%s", memory_id)
        return False

    try:
        memory = await db.get(Memory, mem_uuid)
        if memory is None or memory.archived:
            return False
        if memory.user_id != user_id:
            logger.warning(
                "strengthen_memory: ownership mismatch user_id=%s memory_id=%s",
                user_id,
                memory_id,
            )
            return False

        memory.importance = min(memory.importance + 1.0, MAX_IMPORTANCE)
        memory.last_accessed = datetime.now(timezone.utc)
        await db.commit()
        return True
    except Exception:
        logger.exception(
            "strengthen_memory failed for user_id=%s memory_id=%s", user_id, memory_id
        )
        await db.rollback()
        return False
