"""Forgetting engine: exponential importance decay and archival.

``apply_decay`` reduces the importance of non-core memories based on their age
and ``decay_rate``, then archives (soft-deletes) those that fall below a
threshold. Core memories (``decay_rate=0``) are never decayed or archived.
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Memories with importance below this are archived (soft-deleted).
ARCHIVE_THRESHOLD = 0.1

_DECAY_SQL = text(
    """
    UPDATE memories
    SET importance = importance * EXP(
        -decay_rate * (EXTRACT(EPOCH FROM (NOW() - created_at)) / 86400.0)
    )
    WHERE type <> 'core' AND archived = false
    """
)

_ARCHIVE_SQL = text(
    """
    UPDATE memories
    SET archived = true
    WHERE type <> 'core' AND archived = false AND importance < :threshold
    """
)


async def apply_decay(db_session: AsyncSession) -> dict[str, int]:
    """Apply exponential decay to non-core memories and archive weak ones.

    Uses raw SQL for a single-pass bulk update. Returns a summary dict with the
    number of rows decayed and archived. Commits using the provided session.
    """

    decay_result = await db_session.execute(_DECAY_SQL)
    archive_result = await db_session.execute(
        _ARCHIVE_SQL, {"threshold": ARCHIVE_THRESHOLD}
    )
    await db_session.commit()

    summary = {
        "decayed": decay_result.rowcount or 0,
        "archived": archive_result.rowcount or 0,
    }
    logger.info(
        "apply_decay: decayed=%d archived=%d", summary["decayed"], summary["archived"]
    )
    return summary
