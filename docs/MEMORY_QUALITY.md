# Memory quality

## Kinds and decay

Every memory has a `kind`: `fact`, `event` or `preference`. The kind sets how fast importance decays (per day, exponential). `core` memories never decay.

| Kind | Setting | Default |
|---|---|---|
| fact | `DECAY_RATE_FACT` | 0.005 |
| event | `DECAY_RATE_EVENT` | 0.03 |
| preference | `DECAY_RATE_PREFERENCE` | 0.01 |

The extractor picks the kind. When it is missing, the legacy `type` decides (`episodic` is `event`, `preference` is `preference`, anything else is `fact`). The rate is stored in `memories.decay_rate` at ingestion, so the nightly SQL decay in `app/memory/forgetting.py` needs no change. Rows that existed before the migration keep the `decay_rate` they already had.

Migration `b4c5d6e7f8a9` adds `memories.kind` (default `fact`) and backfills it from `type`.

## Contradictions and history

When a new memory contradicts an existing one, `decide_supersede` (in `app/memory/quality.py`) checks that the new memory is not older and that neither side is an event. Events are history, so they are never superseded. A superseded row keeps its content, gets `superseded=true` and `superseded_by=<new id>`.

Superseded memories are excluded from recall and from the Memories list. To read the chain, call `GET /api/memories/{id}/history` (oldest first). `GET /api/memories/recall?query=...&include_superseded=true` includes them.

## Why a memory was recalled

`GET /api/memories/recall?query=...` returns each memory with a `why` object:

```json
{"similarity": 0.81, "recency": 0.97, "importance": 0.7, "kind": "fact", "score": 0.55, "summary": "fact: similarity 0.81, recency 0.97, importance 0.70"}
```

`score = similarity * importance * recency`, the same formula used to rank candidates in SQL.

## Recall benchmark

`app/memory/recall_benchmark.py` holds fixed cases (diet, superseded city, stale versus recent event, preference).

- Tests: `cd backend && ../.venv/bin/pytest tests/test_recall_benchmark.py tests/test_memory_quality.py` uses deterministic bag-of-words embeddings, no DB or network.
- Script: start `backend/tests/mock_openai_server.py`, set `LLM_PROVIDER=openai`, `LLM_BASE_URL`, `LLM_API_KEY` (any placeholder) and `LLM_EMBEDDING_MODEL`, then run `python scripts/benchmark.py --offline`. Mock embeddings are deterministic but not semantic, so the queries are the exact memory text. Use a real provider to measure semantic recall.
