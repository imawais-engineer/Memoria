# AGENTS.md

## Cursor Cloud specific instructions

### Current repository state (IMPORTANT)

This repository is **documentation-only** right now. It contains just:

- `README.md`
- `docs/MEMORIA_DEVELOPMENT_ROADMAP.md`

There is **no application code, no dependency manifest, no tests, no lint config, and no build system yet.** As the README states, implementation has not started ("Implementation starts with Module 1"). Consequently there is nothing to install, lint, test, build, or run until the code described in the roadmap is scaffolded.

### Intended stack (per `docs/MEMORIA_DEVELOPMENT_ROADMAP.md`)

When implementation begins, the project is planned as:

- **Backend:** Python 3.11+ / FastAPI, run in dev with `uvicorn app.main:app --reload` from `backend/`. Health check at `/health`.
- **Async workers:** Celery + Celery Beat (Redis broker).
- **Data stores:** PostgreSQL with the `pgvector` extension, and Redis.
- **LLM provider:** Qwen via DashScope SDK — requires a `DASHSCOPE_API_KEY` secret. `.env` keys per the roadmap: `DASHSCOPE_API_KEY`, `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`.
- **Frontend (later):** React (Vite) in `frontend/`.

These services (Postgres+pgvector, Redis) and the `DASHSCOPE_API_KEY` secret will be required to run the backend end-to-end once it exists.

### Update script behavior

The registered startup/update script is intentionally **guarded**: it installs Python deps only if a `requirements.txt` (root or `backend/`) exists, and Node deps only if a `package.json` (root or `frontend/`) exists. Today all guards are skipped because none of those files exist yet, so the script is a safe no-op. Once the roadmap layout is scaffolded, the same script will begin installing dependencies without further changes.

### Base tooling available on the VM

- Python 3.12, `pip` 24
- Node 22, `npm` 10
- `git`
- `docker` and `uv` are **not** installed by default; add them if a future module requires them.
