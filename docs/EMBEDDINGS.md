# Embeddings and vector dimensions

Memoria stores memory vectors in `memories.embedding`, a pgvector column of
**1024 dimensions** by default (Qwen `text-embedding-v3`). The column size is
fixed by the Alembic migrations and is not changed by configuration alone.

## Settings

| Variable | Meaning |
|---|---|
| `LLM_EMBEDDING_MODEL` | Embedding model id on the OpenAI-compatible endpoint |
| `EMBEDDING_DIM` | Vector length the app expects (default `1024`) |
| `LLM_EMBEDDING_SEND_DIMENSIONS` | Send `dimensions=EMBEDDING_DIM` with requests (OpenAI `text-embedding-3-*` can shrink output to 1024) |

## Safety checks

- Every vector returned by `get_embedding` is length-checked against
  `EMBEDDING_DIM`; a mismatch raises `EmbeddingDimensionError` with a message
  naming both sizes.
- At startup the API compares `EMBEDDING_DIM` with the live column size
  (`pg_attribute.atttypmod`) and refuses to start on a mismatch. If the database
  is unreachable or not migrated yet the check is skipped with a warning.

## Staying on 1024 (no migration)

Choose a model that returns 1024 dimensions, or one that supports the
`dimensions` parameter (set `LLM_EMBEDDING_SEND_DIMENSIONS=true`). If you change
to a different model of the same size, run the re-embed script because vectors
from different models are not comparable.

## Changing the dimension

1. Back up the database.
2. Create an Alembic migration (from `backend/`, keep a single head) that drops
   the vector indexes, alters the column and recreates the indexes, for example:

   ```python
   op.execute("UPDATE memories SET embedding = NULL")  # only if the column is nullable
   op.execute("ALTER TABLE memories ALTER COLUMN embedding TYPE vector(1536) USING NULL")
   ```

   The column is `NOT NULL` today, so either relax it in the migration and
   restore it after re-embedding, or truncate memories you can regenerate.
3. Update `EMBEDDING_DIM` in `app/memory/models.py` to the same value and set
   the `EMBEDDING_DIM` environment variable.
4. Run `alembic upgrade head`, then `python scripts/reembed.py` from `backend/`.
5. Restart the API and Celery workers.
