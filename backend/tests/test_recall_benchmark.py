"""Recall benchmark with deterministic embeddings (no DB, no network)."""

import pytest

from app.memory.recall_benchmark import bow_embedding, run_recall_cases


async def _embed(text: str) -> list[float]:
    return bow_embedding(text)


@pytest.mark.asyncio
async def test_recall_benchmark_passes_all_cases():
    report = await run_recall_cases(_embed)
    failed = [c for c in report["cases"] if not c["passed"]]
    assert not failed, failed
    assert report["recall_at_1"] == 1.0


@pytest.mark.asyncio
async def test_superseded_memory_never_recalled():
    report = await run_recall_cases(_embed)
    city = next(c for c in report["cases"] if c["case"] == "supersede_city")
    assert "paris" not in city["ranking"]
