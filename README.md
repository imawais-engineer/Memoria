# Memoria – Self-Evolving Personal AI with Human-like Memory

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.11x-009688?logo=fastapi&logoColor=white)
![Qwen Cloud](https://img.shields.io/badge/Qwen%20Cloud-DashScope-6c8cff)
![Alibaba Cloud](https://img.shields.io/badge/Alibaba%20Cloud-ApsaraDB%20%2B%20ECS-FF6A00?logo=alibabacloud&logoColor=white)
![License](https://img.shields.io/badge/License-Apache%202.0-blue)

> A personal AI agent that remembers across sessions, learns your preferences, and gracefully forgets outdated information – built on Qwen Cloud and Alibaba Cloud.

**Track:** Track 1 – MemoryAgent

---

## Features

- **Persistent memory** – facts extracted from conversations are embedded and stored in PostgreSQL + pgvector.
- **Cross-session continuity** – recall what you told the agent in earlier, separate sessions.
- **Smart retrieval** – hybrid ranking (vector similarity × importance × recency) with a token budget, always surfacing `core` facts first.
- **Autonomous forgetting** – daily exponential decay archives stale, low-importance memories.
- **Session summaries** – rolling summaries keep long conversations coherent and persist as memories.
- **Manual forget** – delete any memory from the dashboard (right to be forgotten).
- **Admin dashboard** – a React UI to chat and inspect/curate stored memories.

---

## Architecture overview

Memoria is a modular FastAPI backend plus a React dashboard:

- A chat turn hits **`POST /chat`**, which loads the short-term **Redis** session, retrieves relevant long-term memories from **PostgreSQL + pgvector**, and asks **Qwen (DashScope)** for a reply.
- New facts are extracted asynchronously by a **Celery** worker (Qwen function calling), embedded with `text-embedding-v3`, and stored.
- Scheduled **Celery Beat** jobs handle **decay** (daily) and **consolidation** (weekly, via Qwen-Max clustering + summarization).

See the full component breakdown and sequence diagram in **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

---

## Quick start

### 1. Clone & configure

```bash
git clone https://github.com/imawais-engineer/Memoria.git
cd Memoria
cp .env.example .env
# edit .env — set DASHSCOPE_API_KEY (and DASHSCOPE_BASE_URL if using the
# international DashScope endpoint, e.g. https://dashscope-intl.aliyuncs.com/api/v1)
```

### 2a. Run with Docker Compose (backend + Postgres/pgvector + Redis + workers)

```bash
docker compose up --build -d
docker compose run --rm backend alembic upgrade head   # apply DB migrations
# backend now on http://localhost:8000  (health: /health, docs: /docs)
```

Then start the dashboard:

```bash
cd frontend && npm install && npm run dev   # http://localhost:5173
```

### 2b. Run locally (without Docker)

Requires Python 3.12, Node 18+, PostgreSQL 16 with the `pgvector` extension, and Redis.

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload           # http://localhost:8000

# Background workers (separate shells, from backend/)
celery -A celery_app worker --loglevel=info
celery -A celery_app beat   --loglevel=info

# Frontend (separate shell)
cd frontend && npm install && npm run dev   # http://localhost:5173
```

---

## Demo video

📺 **Demo:** _YouTube link coming soon_ &nbsp;•&nbsp; script: **[DEMO_SCRIPT.md](DEMO_SCRIPT.md)**

---

## Tech stack

| Layer | Technology |
|---|---|
| API | FastAPI (async), Uvicorn |
| LLM | Qwen via DashScope (`qwen-plus`, `qwen-max`, `text-embedding-v3`) |
| Vector store | PostgreSQL 16 + pgvector |
| Cache / sessions | Redis |
| Background jobs | Celery + Celery Beat |
| Frontend | React (Vite) |
| Deployment | Alibaba Cloud (ECS + ApsaraDB), Terraform — see [infrastructure/acs_deployment.tf](infrastructure/acs_deployment.tf) |

---

## Project layout

```
backend/          FastAPI app, memory subsystem, Celery, Alembic, Dockerfile
frontend/         React (Vite) admin dashboard
infrastructure/   Terraform for Alibaba Cloud deployment
docs/             Architecture & development roadmap
```

---

## Roadmap

The module-by-module build plan lives in **[docs/MEMORIA_DEVELOPMENT_ROADMAP.md](docs/MEMORIA_DEVELOPMENT_ROADMAP.md)**.

## License

Licensed under the **Apache License 2.0** — see [LICENSE](LICENSE).
