"""Startup check: configured EMBEDDING_DIM must match the pgvector column."""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.llm.base import EmbeddingDimensionError

logger = logging.getLogger(__name__)

_COLUMN_DIM_SQL = text(
    "SELECT a.atttypmod FROM pg_attribute a "
    "WHERE a.attrelid = 'memories'::regclass AND a.attname = 'embedding'"
)


def compare_dims(configured: int, column_dim: int | None) -> None:
    """Raise if ``column_dim`` is known and differs from ``configured``."""

    if column_dim is not None and column_dim > 0 and column_dim != configured:
        raise EmbeddingDimensionError(
            f"EMBEDDING_DIM={configured} but memories.embedding is vector({column_dim}). "
            "Set EMBEDDING_DIM to the column size, or migrate the column and "
            "re-embed (see docs/EMBEDDINGS.md)."
        )


async def check_embedding_dim(engine: AsyncEngine, configured: int) -> None:
    """Compare against the live column. Skips quietly if the DB is unreachable
    or the table does not exist yet (migrations not applied)."""

    try:
        async with engine.connect() as conn:
            column_dim = (await conn.execute(_COLUMN_DIM_SQL)).scalar_one_or_none()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Embedding dimension check skipped (%s)", type(exc).__name__)
        return
    compare_dims(configured, column_dim)
    logger.info("Embedding dimension OK (%s)", configured)
