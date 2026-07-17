# Memoria – Self‑Evolving Personal AI with Human‑like Memory

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.11x-009688?logo=fastapi&logoColor=white)
![Qwen Cloud](https://img.shields.io/badge/Qwen%20Cloud-DashScope-6c8cff)
![Alibaba Cloud](https://img.shields.io/badge/Alibaba%20Cloud-ApsaraDB%20%2B%20ECS-FF6A00?logo=alibabacloud&logoColor=white)
![License](https://img.shields.io/badge/License-Apache%202.0-blue)

> A production‑grade MemoryAgent that remembers, forgets, resolves conflicts, and reflects on user knowledge – built on Qwen Cloud.

**Track:** Track 1 – MemoryAgent

**Live demo:** [http://20.219.193.66](http://20.219.193.66)

---

## Features

- **Persistent memory** – facts extracted from conversations are embedded (`text-embedding-v3`, 1024-dim) and stored in PostgreSQL + pgvector.
- **Cross‑session recall** – retrieve what you told the agent in earlier, separate sessions via hybrid ranking (vector similarity × importance × recency).
- **MCP skills** – expose memory tools (`get_core_memories`, `get_user_preferences`, `forget_memory`, `strengthen_memory`) at `GET /mcp/memory-skills` for external agents.
- **Autonomous forgetting & consolidation** – daily exponential decay archives stale memories; weekly Qwen‑Max clustering consolidates related facts into concise summaries.
- **Conflict detection** – new facts that contradict stored memories are flagged and superseded automatically during ingestion.
- **Reflective insights** – periodic Qwen reflection surfaces higher‑level patterns about the user and injects them into the system prompt.
- **Thumbs‑up/down feedback** – rate assistant replies to strengthen or weaken the memories that informed them (`POST /api/feedback`).
- **Structured output** – Qwen structured JSON responses power consolidation, reflection, and conflict resolution with schema fallbacks.
- **Benchmark‑proven 77.6% improvement** – 12‑scenario evaluation shows memory‑augmented replies score **77.6% higher** on average (see [Benchmark](#benchmark) below).
- **Markdown + LaTeX chat rendering** – assistant replies render rich Markdown and KaTeX math (`$...$`, `$$...$$`) in the dashboard.
- **Multimodal generation in chat** – use `/imagine`, `/gen_video`, and `/gen_voice` slash commands in chat for inline images (`wan2.1-t2i-plus`), videos (`wan2.1-t2v-turbo`), and voice overviews (Qwen summary + `qwen3-tts-flash`). All media uses DashScope default settings (no per-user size/duration controls). Image/video quotas: default 5 images / 2 videos per user; voice has no limit.
- **Chat model switcher** – choose among `qwen-plus`, `qwen-max`, `qwq-plus`, and `qwen-turbo` per session via `GET /api/models` and the chat composer dropdown.
- **Deployment on Azure + Alibaba Cloud Terraform proof** – live instance on Azure; full stack IaC for Alibaba Cloud in [`infrastructure/acs_deployment.tf`](infrastructure/acs_deployment.tf).

---

## Architecture

Memoria is a modular FastAPI backend plus a React dashboard:

- A chat turn hits **`POST /chat`**, which loads the short‑term **Redis** session, retrieves relevant long‑term memories from **PostgreSQL + pgvector**, and asks **Qwen (DashScope)** for a reply.
- New facts are extracted asynchronously by a **Celery** worker (Qwen function calling), embedded, and stored — with conflict detection and supersession.
- Scheduled **Celery Beat** jobs handle **decay** (daily) and **consolidation** (weekly).
- Reflection runs in the background every 10th user message; MCP tools let external agents query and curate memory.

See the full component breakdown, sequence flows, and Mermaid diagram in **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

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

See [`.env.example`](.env.example) for all supported variables (`DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `DEMO_API_TOKEN`, etc.).

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

Open **http://localhost:5173** — you'll see the Memoria public landing dashboard at `/`. Click **Get Started** (top-right) to open `/auth`, then sign up or log in (username + favorite book). After login you're taken to `/app` (Chat, Memory, Persona). The chat UI uses lazy session creation: new chats appear in the sidebar only after you send the first message. Use the sidebar for **Personal Intelligence**, **New Chat**, and **Memoryless** private sessions. In chat, try `/imagine`, `/gen_video`, or `/gen_voice` for inline media; the composer also includes a **model switcher** (`qwen-plus`, `qwen-max`, `qwq-plus`, `qwen-turbo`).

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

## Benchmark

Memoria ships a reproducible benchmark suite (`scripts/benchmark.py`) that compares Qwen replies **with** vs **without** injected user memories across 12 realistic scenarios (dietary restrictions, allergies, preferences, goals).

| Metric | Without memory | With memory |
|---|---:|---:|
| Average accuracy | 0.58 | **0.90** |
| Average composite score (accuracy + safety + coherence) | 0.64 | **0.92** |
| Average improvement | — | **+77.6%** |

| Scenario | Improvement |
|---|---:|
| Recommend a restaurant for Friday dinner | +211% |
| What should I cook tonight? | +100% |
| Plan a healthy lunch for tomorrow | +58% |
| Help me choose a meal prep plan for the week | +460% |
| What should I do on a rainy Saturday? | +42% |
| *(7 more scenarios in results file)* | varies |

Full results: [`scripts/benchmark_results.json`](scripts/benchmark_results.json). Re‑run with:

```bash
cd backend && python ../scripts/benchmark.py
```

---

## Demo video

📺 **[YouTube URL TBD]** &nbsp;•&nbsp; script: **[DEMO_SCRIPT.md](DEMO_SCRIPT.md)**

---

## Tech stack

| Layer | Technology |
|---|---|
| API | FastAPI (async), Uvicorn |
| LLM | Qwen via DashScope (`qwen-plus`, `qwen-max`, `text-embedding-v3`) |
| Vector store | PostgreSQL 16 + pgvector |
| Cache / sessions | Redis |
| Background jobs | Celery + Celery Beat |
| Frontend | React (Vite), react-markdown |
| Deployment | Azure (live demo) + Alibaba Cloud Terraform — [`infrastructure/acs_deployment.tf`](infrastructure/acs_deployment.tf) |

---

## Project layout

```
backend/          FastAPI app, memory subsystem, MCP skills, Celery, Alembic
frontend/         React (Vite) dashboard — public landing page, auth, chat, memory, persona
infrastructure/   Terraform for Alibaba Cloud deployment
scripts/          Benchmark suite and results
docs/             Architecture, roadmap, upgrade notes
```

---

## Further reading

- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — system diagram and data flows
- **[DEMO_SCRIPT.md](DEMO_SCRIPT.md)** — 3‑minute hackathon demo script
- **[BLOG_POST.md](BLOG_POST.md)** — short project narrative for Medium/dev.to
- **[docs/MEMORIA_DEVELOPMENT_ROADMAP.md](docs/MEMORIA_DEVELOPMENT_ROADMAP.md)** — module‑by‑module build plan

---

## License

Licensed under the **Apache License 2.0** — see [LICENSE](LICENSE).
