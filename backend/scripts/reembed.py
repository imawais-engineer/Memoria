#!/usr/bin/env python3
"""Re-embed every memory with the currently configured embedding model.

Run from ``backend/`` after changing the embedding model (and, if the vector
size changed, after migrating the column; see docs/EMBEDDINGS.md)::

    python scripts/reembed.py [--batch-size 50] [--dry-run]

Reads LLM_* / DATABASE_URL settings from the environment. The script is
idempotent: rerunning simply recomputes the vectors.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402

from app.core.dashscope_client import get_embedding  # noqa: E402
from app.core.database import AsyncSessionLocal, engine  # noqa: E402
from app.core.llm.dimcheck import check_embedding_dim  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.memory.models import Memory  # noqa: E402


async def reembed(batch_size: int, dry_run: bool) -> int:
    settings = get_settings()
    # Fails fast if EMBEDDING_DIM does not match the column.
    await check_embedding_dim(engine, settings.embedding_dim)
    done = 0
    async with AsyncSessionLocal() as session:
        ids = (await session.execute(select(Memory.id).order_by(Memory.created_at))).scalars().all()
        print(f"{len(ids)} memories to re-embed (dim={settings.embedding_dim})")
        for start in range(0, len(ids), batch_size):
            for memory_id in ids[start : start + batch_size]:
                memory = await session.get(Memory, memory_id)
                if memory is None:
                    continue
                vector = await get_embedding(memory.content)  # validated length
                if not dry_run:
                    memory.embedding = vector
                done += 1
            if not dry_run:
                await session.commit()
            print(f"  {done}/{len(ids)}")
    await engine.dispose()
    return done


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--dry-run", action="store_true", help="embed but do not write")
    args = parser.parse_args()
    asyncio.run(reembed(args.batch_size, args.dry_run))


if __name__ == "__main__":
    main()
