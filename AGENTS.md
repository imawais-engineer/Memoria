# AGENTS.md

## Cursor Cloud specific instructions

### Current repository state (IMPORTANT)

Memoria is a **fully implemented** MemoryAgent stack (Modules 1–10). The Python
backend lives under `backend/`:

- `backend/requirements.txt` — backend dependencies.
- `backend/app/main.py` — FastAPI app with health, auth, chat (incl. SSE stream),
  memories, tasks, generate, sessions, feedback, MCP catalog.
- `backend/app/config.py` — `pydantic-settings` config; resolves `.env` from the
  repo root regardless of the current working directory.
- `backend/app/memory/` — ingestion, retrieval, forgetting, consolidation,
  conflict detection, reflection.
- `backend/app/services/agent_service.py` — chat orchestration; system prompt
  includes memory context, persona, capabilities, identity, and product knowledge base.
- `backend/app/services/memoria_knowledge.py` — static architecture/feature KB for the AI.
- `backend/celery_app/` — workers + Beat (decay daily 03:00 UTC, consolidation weekly Sun 04:00 UTC).

### Running the backend (dev)

- The update script installs `backend/requirements.txt`. If running by hand,
  create a venv and `pip install -r backend/requirements-dev.txt` (runtime
  deps plus pytest; use `scripts/requirements.txt` for the benchmark; needs the
  `python3.12-venv` system package for `python3 -m venv`).
- Start the dev server **from the `backend/` directory** so the `app` package
  imports resolve: `uvicorn app.main:app --reload --port 8000`.
- Verify: `curl localhost:8000/health` returns `200` with
  `{"status":"ok","service":"memoria","version":"0.1.0"}`. Swagger UI at `/docs`.
- Full functionality requires `DASHSCOPE_API_KEY`, Postgres (pgvector), and Redis.

### Tests

- Run from `backend/`: `../.venv/bin/pytest -q -rs` (or `pytest -q -rs` in an activated venv).
- DB-less unit tests (`test_security.py`, `test_forgetting_math.py`, `test_celery_schedule.py`,
  `test_retrieval_packing.py`, `test_ingestion_parsing.py`, `test_consolidation_clustering.py`)
  mock DashScope/Redis and run anywhere.
- DB-backed API tests use the `db_session_factory` fixture and need Postgres with pgvector at
  `TEST_DATABASE_URL`; they are skipped automatically when it is unreachable.
- CI: `.github/workflows/backend-tests.yml` runs everything with pgvector + Redis services.

### Frontend (`frontend/`, dashboard + landing)

- Vite + React (JS) app. Run from `frontend/`: `npm run dev` (dev server on
  port 5173). Vite proxies `/chat` and `/api` to the backend on port 8000.
- **Routes:** `/` landing page → `/auth` signup/login → `/app` dashboard.
- **Sidebar:** Memories, Persona, Tasks, Media, Recent Chats, profile menu
  (Settings, Help, Feedback, About).
- **Chat:** SSE streaming (`POST /chat/stream`), slash commands (type `/` for help
  table), Personal Intelligence toggle, MemoryLess mode on new chats, model switcher.
- **Memories tab:** `GET /api/memories`, `DELETE /api/memories/{id}` with
  `X-API-Token` header matching `DEMO_API_TOKEN` (default `memoria-demo-token`).

### Database & migrations (Alembic)

- DB-backed work needs local **PostgreSQL 16 with the `pgvector` extension**.
- Default DSN: `postgresql+asyncpg://user:pass@localhost/memoria`.
- Run Alembic **from `backend/`** (e.g. `alembic upgrade head`).
- Embedding dimension = **1024** (`text-embedding-v3`). Memory types include
  `core`, `episodic`, `semantic`, `procedural`, `goal`, `preference`.

### Celery workers (`celery_app/`)

- Start worker **from `backend/`**: `celery -A celery_app worker --loglevel=info`.
- Beat: `celery -A celery_app beat --loglevel=info`.
- Put secrets in repo-root `.env` for workers started in separate shells.

### LLM provider layer (`app/core/llm/`, facade `app/core/dashscope_client.py`)

- Any OpenAI-compatible API: set `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_CHAT_MODEL`
  (see `docs/LLM_PROVIDERS.md`). Without `LLM_BASE_URL` DashScope is used.
- Keep importing `call_qwen_chat`, `stream_qwen_chat`, `get_embedding` etc. from
  `app.core.dashscope_client`; tests patch those names.
- Tests use `backend/tests/mock_openai_server.py` (fixture `mock_llm_server`).
  Never put API keys in files; read from env only.
- Embedding size is `EMBEDDING_DIM` (default 1024); see `docs/EMBEDDINGS.md`.

### DashScope / Qwen (`app/core/llm/dashscope_provider.py`)

- Set `DASHSCOPE_API_KEY` and `DASHSCOPE_BASE_URL` for international region
  (e.g. `https://dashscope-intl.aliyuncs.com/api/v1`).
- Chat model: `qwen-plus` (not `qwen3-plus`). Embeddings: `text-embedding-v3` (1024 dims).

### Hackathon submission assets

- Architecture diagram: `Submission Files/architecture.html`
- Full architecture docs: `docs/ARCHITECTURE.md`
- E2E verification: `scripts/e2e_verification.py`

### Base tooling available on the VM

- Python 3.12, `pip` 24
- Node 22, `npm` 10
- `git`
- `docker` and `uv` are **not** installed by default; add them if required.
