# Memoria — Devpost Project Story

**Live demo:** [http://20.219.193.66](http://20.219.193.66)  
**Repository:** [github.com/imawais-engineer/Memoria](https://github.com/imawais-engineer/Memoria)

---

## Inspiration

Most AI assistants today are fundamentally stateless. Every conversation starts from a blank slate: you tell a chatbot you're allergic to peanuts on Monday, and by Wednesday it cheerfully recommends pad thai with crushed peanuts. The model didn't forget — it never had long-term memory in the first place. That limitation makes genuine personalisation impossible. Without durable knowledge about who you are, what you prefer, and what you've already told the system, every reply is generic.

We built **Memoria** around a different vision: a personal AI with **human-like memory** — one that remembers what matters, forgets what fades, resolves contradictions, and evolves its understanding of you over time. Real memory isn't just a bigger context window; it requires extraction, prioritisation, decay, consolidation, and reflection — the same lifecycle that makes human memory useful rather than overwhelming.

The **Qwen Cloud Hackathon, Track 1 – MemoryAgent** challenged us to go beyond simple retrieval-augmented generation and deliver a **memory-efficient, production-ready MemoryAgent**. We took that challenge seriously: Memoria is not a demo prompt hack but a full-stack system with autonomous background workers, vector search, conflict resolution, and quantitative proof that memory makes AI decisions measurably better. Our goal was to show judges — and users — that persistent, well-managed memory transforms an assistant from a clever chatbot into a true personal companion.

---

## What it does

Memoria is a self-evolving personal AI that remembers, forgets, and reflects. Here is what it delivers today:

**Persistent multi-session memory with multi-tier storage**

Memoria organises knowledge across three deliberate tiers:

- **Session Memory** (Redis) — the last 10 messages of the active chat, always included in the model context for conversational continuity.
- **Personal Memory** (PostgreSQL 16 + pgvector) — user-centric facts (preferences, allergies, goals, identity) extracted from conversations, embedded with `text-embedding-v3` (1024 dimensions), ranked by hybrid scoring (vector similarity × importance × recency), and subject to decay, consolidation, and conflict resolution.
- **Context Archive** (PostgreSQL `chat_messages` table) — full transcripts of non-MemoryLess sessions, searchable on demand via `GET /api/search-archive` without polluting routine retrieval.

**Autonomous memory lifecycle: extraction, embedding, decay, consolidation**

After each chat turn, a Celery worker calls Qwen-Plus with function calling to extract structured memories (`core`, `episodic`, `semantic`, `procedural`). Each fact is embedded and stored. Daily Celery Beat jobs apply exponential importance decay and archive stale memories (03:00 UTC). Weekly consolidation clusters similar memories (cosine similarity ≥ 0.75) and uses Qwen-Max to synthesise concise summaries linked via `parent_id` and `is_consolidated` flags.

**Personal Intelligence toggle (global memory access)**

Users control whether the agent can access **all** Personal Memories across every session (`global_memory_enabled`) or only the current session plus essential facts (`importance >= 0.9`). The toggle lives in the sidebar and is reflected in the system prompt so the model knows its memory scope.

**Memory-Less incognito mode**

The 🕶️ **Memoryless** button starts a private session: no Personal Memory is read or written, no Context Archive is created, and Personal Intelligence is disabled. A confirmation modal and in-chat banner make the privacy boundary explicit — ideal for sensitive one-off questions.

**MCP server exposing memory skills to external agents**

Memoria exposes four Qwen-compatible MCP tools at `GET /mcp/memory-skills`: `get_core_memories`, `get_user_preferences`, `forget_memory`, and `strengthen_memory`. External agents can discover, invoke, and curate a user's memory without coupling to Memoria's chat API — turning memory into a reusable skill for any Qwen agent.

**Conflict detection & versioning**

During ingestion, new facts are checked against semantically similar existing memories (pgvector similarity ≥ 0.7). Qwen-Plus structured JSON output (`contradiction` + `reason`) determines whether statements truly conflict; when they do, older memories are marked `superseded` and linked via `version_id`.

**Reflective memory layer**

Every 10th user message in a session triggers background reflection: Qwen analyses active memories and stores a high-importance semantic insight (`importance = 9.0`) with extracted `traits` in metadata — surfacing patterns like "this user values efficiency" for future personalisation.

**User feedback (thumbs-up/down) that adjusts memory importance**

Chat replies include thumbs-up and thumbs-down controls. Positive feedback boosts the importance of memories that informed the reply (`POST /api/feedback`); negative feedback weakens them — closing the loop between user satisfaction and memory ranking.

**Persona customisation**

Users configure response length (Concise / Balanced / Detailed), tone (Professional, Friendly, Educational, Witty, or Custom), and behaviour traits (Cautious, Encouraging, Direct, or Custom). Persona settings are stored on the user profile and injected into the system prompt via `format_persona_prompt()`.

**Structured JSON output for consolidation, reflection, and conflict**

DashScope `response_format` with `json_schema` enforces reliable structured responses: consolidation returns `{summary, key_themes}`, reflection returns `{reflection, traits}`, and conflict detection returns `{contradiction, reason}` — with schema fallbacks when parsing fails.

**Markdown + LaTeX rendering in chat**

Assistant replies render rich Markdown (bold, lists, tables via `remark-gfm`) and mathematical equations (inline `$...$` and block `$$...$$` via `remark-math` + `rehype-katex`). Preprocessing handles Qwen's `<br>` tags, LaTeX delimiter quirks, and common spacing issues before rendering.

**Authentication (soft-password via favorite book)**

Judge-friendly signup and login use **username + favorite book** as a memorable soft password — no email verification friction. Each user gets a unique profile (first name, last name, username) and all memories are scoped to `user_id`.

**Benchmark-proven 77.6% improvement in decision accuracy**

Our reproducible benchmark suite (`scripts/benchmark.py`) compares Qwen-Plus replies with and without injected user memories across 12 realistic scenarios (dietary restrictions, allergies, weekend plans, learning goals). Results in `scripts/benchmark_results.json`:

| Metric | Without memory | With memory |
|---|---:|---:|
| Average accuracy | 0.58 | **0.90** |
| Average composite score | 0.64 | **0.92** |
| Average improvement | — | **+77.6%** |

Standout gains include **+460%** on meal-prep planning, **+211%** on restaurant recommendations, and **+100%** on "what should I cook tonight?" — scenarios where the memory-less baseline had zero user context.

**Live deployment on Alibaba Cloud ECS with ApsaraDB for PostgreSQL & Redis**

The full stack is containerised with Docker Compose and deployable via Terraform on Alibaba Cloud (`infrastructure/acs_deployment.tf`): an ECS instance (Ubuntu 22.04) runs the FastAPI backend in Docker, backed by **ApsaraDB RDS for PostgreSQL 16** (pgvector-capable) and **ApsaraDB for Redis** (KVStore), with VPC networking and security groups exposing ports 22 and 8000. The live demo is available at [http://20.219.193.66](http://20.219.193.66).

---

## How we built it

Memoria is a modular **FastAPI backend** plus a **React (Vite) dashboard**, designed so interactive chat stays fast while durable memory work runs asynchronously.

**Backend: Python FastAPI, SQLAlchemy async, PostgreSQL 16 + pgvector**

The API layer (`backend/app/main.py`) exposes `/health`, `/chat`, `/auth`, `/api/memories`, `/api/feedback`, `/api/sessions`, `/api/search-archive`, and `/mcp/memory-skills`. SQLAlchemy async sessions talk to PostgreSQL; Alembic manages migrations including the pgvector extension and the `memories`, `users`, `chat_sessions`, and `chat_messages` tables. Hybrid retrieval in `retrieval.py` embeds the user query, scores candidates by `(similarity × importance × recency)`, prioritises `core` memories, and packs context under a token budget.

**Memory pipeline: DashScope (Qwen-Plus, Qwen-Max, text-embedding-v3)**

- **Qwen-Plus** — chat replies, memory extraction via function calling, conflict detection, and reflection.
- **Qwen-Max** — weekly consolidation summaries with structured JSON output.
- **text-embedding-v3** — 1024-dimensional embeddings for both memories and queries.

The DashScope client (`dashscope_client.py`) wraps synchronous SDK calls in `asyncio.to_thread`, configures the international endpoint via `DASHSCOPE_BASE_URL`, and provides `call_qwen_structured()` for schema-enforced JSON responses.

**Celery workers for background memory tasks, Redis for session/broker**

Redis serves triple duty: Session Memory store (last 10 messages per chat), Celery message broker, and Celery result backend. Three worker types run in separate containers:

- **Ingestion worker** — `extract_memories_task` after each chat turn.
- **Decay worker** — daily `apply_decay` at 03:00 UTC.
- **Consolidation worker** — weekly `consolidate_memories` on Saturday 04:00 UTC.

**Frontend: React + Vite, react-markdown, KaTeX**

The dashboard (`frontend/`) includes a landing page with benchmark highlights, auth flow, sidebar with session list / Personal Intelligence toggle / Memoryless button, chat with Markdown+LaTeX rendering and feedback buttons, a Memory tab with stats cards and type distribution chart, and a Persona settings panel. Vite proxies `/chat` and `/api` to the backend on port 8000.

**Deployment: Docker Compose, Alibaba Cloud ECS (Terraform proof available)**

Local development uses `docker-compose.yml` (PostgreSQL/pgvector, Redis, backend, Celery worker, Celery Beat). Production deployment is defined in `infrastructure/acs_deployment.tf` — provisioning ECS, ApsaraDB PostgreSQL, ApsaraDB Redis, VPC, and injecting secrets (including `DASHSCOPE_API_KEY`) into the backend container via cloud-init.

**MCP skills server, structured output via DashScope `response_format`**

Four async MCP tools in `backend/app/mcp/memory_skill.py` implement ownership-checked memory operations. Structured pipelines use DashScope's `result_format="json"` with explicit JSON schemas, keeping consolidation themes, reflection traits, and conflict reasons machine-parseable.

**Three-tier memory architecture in practice**

When a user sends a message:

1. **Session Memory** — Redis provides the last 10 turns for immediate conversational context.
2. **Personal Memory** — `retrieve_context_and_ids()` queries pgvector (respecting PI toggle and MemoryLess isolation) and packs the most relevant facts.
3. **Context Archive** — the exchange is persisted to `chat_messages` (unless MemoryLess); explicit recall uses token-guarded archive search, not routine injection.

After the reply, ingestion runs in Celery, reflection may trigger on the 10th message, and scheduled jobs handle decay and consolidation — completing the capture → embed → retrieve → consolidate → decay lifecycle documented in `docs/ARCHITECTURE.md`.

---

## Challenges we ran into

**Embedding dimension mismatch (1536 vs 1024)**

Our initial schema assumed `text-embedding-v2` dimensions (1536), but the international DashScope account only permitted `text-embedding-v3` at **1024 dimensions** — and `text-embedding-v2` returned `AccessDenied`. Vector inserts failed silently until we traced the mismatch. We fixed it with Alembic migration `0c753efdf9dc`, altering the `memories.embedding` column from `Vector(1536)` to `Vector(1024)` and ensuring all ingestion and retrieval code used the same model.

**DashScope international endpoint authentication**

The provided API key was for the **international** region, but the DashScope SDK defaults to the Beijing endpoint — returning `401 InvalidApiKey` with no obvious hint. We added `DASHSCOPE_BASE_URL=https://dashscope-intl.aliyuncs.com/api/v1` to config and applied it in `get_dashscope_client()` so every process (API server, Celery workers) hits the correct endpoint.

**Model availability (qwen3-plus not available, switching to qwen-plus)**

The roadmap specified `qwen3-plus`, but our account returned `400 InvalidParameter: Model not exist`. After testing available models, we standardised on **`qwen-plus`** for chat, extraction, conflict detection, and reflection, and **`qwen-max`** for consolidation — both fully supporting function calling and structured JSON output.

**Markdown rendering (tables, LaTeX, `<br>` tags) requiring multiple plugins**

Qwen's replies often include Markdown tables, inline HTML `<br>` line breaks, and LaTeX in mixed delimiter formats (`$...$`, `\(...\)`, `\[...\]`). A single `react-markdown` pass wasn't enough. We added `remark-gfm` for tables, `remark-math` + `rehype-katex` for equations, and a preprocessing layer in `Chat.jsx` that normalises `<br>` tags, fixes common LaTeX spacing typos, and converts alternate delimiters before rendering.

**Maintaining performance while introducing conflict detection and reflection**

Every new memory now triggers a pgvector similarity search plus a structured Qwen call for contradiction checking — and reflection adds another LLM round-trip every 10 messages. We kept chat latency acceptable by running conflict detection and reflection **asynchronously** inside Celery ingestion (not on the request path), using candidate limits (top 20 similar memories, top 50 for retrieval) and structured JSON with schema fallbacks to avoid retry loops.

**Port and venv issues during Alibaba Cloud deployment**

Standing up the stack on ECS surfaced practical DevOps friction: security group rules needed explicit ports 22 and 8000, Docker Compose service discovery differed from localhost DSNs, and Celery workers started in separate shells didn't inherit injected secrets. We documented the gotchas in `AGENTS.md` — use repo-root `.env` for keys, run Alembic from `backend/`, and ensure workers share the same `DATABASE_URL` and `REDIS_URL` as the API container. Python venv setup on Ubuntu required the `python3.12-venv` system package before `pip install` would succeed.

---

## Accomplishments that we're proud of

**The full memory lifecycle — decay, consolidation, reflection — all working**

Memoria implements every stage of human-like memory management: capture via Qwen function calling, hybrid pgvector retrieval, daily exponential decay, weekly Qwen-Max consolidation with `parent_id` linking, structured conflict supersession, and periodic reflection that stores trait-labelled insights. This isn't a slide-deck architecture — it's running in production with Celery Beat schedules and Alembic migrations.

**MCP integration turning Memoria into a reusable skill for any Qwen agent**

By exposing `get_core_memories`, `get_user_preferences`, `forget_memory`, and `strengthen_memory` over a standard HTTP tool catalog, we made Memoria's memory layer interoperable. Any external agent that speaks Qwen's tool-calling protocol can query and curate user knowledge without reimplementing extraction or storage.

**77.6% benchmark improvement proving memory's real value**

We didn't just claim memory helps — we measured it. Twelve scenarios with a synthetic user profile (peanut/shellfish allergies, vegetarian diet, hiking and ML interests) show memory-augmented Qwen replies scoring **77.6% higher** on average, with dramatic gains where context was essential (meal prep: +460%, restaurant pick: +211%).

**Clean, professional UI with auth, sidebar sessions, persona, toggles**

The dashboard delivers a judge-ready experience: landing page with benchmark stats, username + favorite-book auth, lazy session creation (chats appear in the sidebar only after the first message), Personal Intelligence toggle, Memoryless incognito mode with confirmation modal, thumbs-up/down feedback, persona customisation, and a Memory tab with aggregate statistics and type distribution chart.

**Successful live deployment on Alibaba Cloud infrastructure**

Full infrastructure-as-code in `infrastructure/acs_deployment.tf` provisions ECS, ApsaraDB PostgreSQL (pgvector), and ApsaraDB Redis on Alibaba Cloud — demonstrating production readiness beyond a local Docker demo. The stack is live at [http://20.219.193.66](http://20.219.193.66).

**Modular, well-documented codebase ready for open-source contributions**

Memoria ships with `docs/ARCHITECTURE.md` (Mermaid diagram + data flows), `docs/UPGRADE_MEMORIA.md` (module-by-module build plan), `AGENTS.md` (cloud dev instructions), Apache 2.0 license, and a clean separation between `backend/app/memory/`, `backend/app/mcp/`, `backend/app/api/`, and `frontend/src/components/`. New contributors can follow the roadmap and extend individual modules independently.

---

## What we learned

**Designing efficient, human-like memory is harder than simple RAG**

Naive "embed everything and retrieve top-k" breaks down quickly: memories go stale, contradict each other, and overwhelm the context window. Memoria taught us that a production MemoryAgent needs **importance scores, decay rates, consolidation, conflict resolution, and tiered storage** — not just a vector index. Hybrid ranking (similarity × importance × recency) with greedy token-budget packing outperformed flat retrieval in both benchmark scores and subjective reply quality.

**Qwen's tool-calling and structured output are powerful for reliability**

Function calling for memory extraction (`extract_memories` tool) and `json_schema` enforcement for consolidation, reflection, and conflict detection eliminated most free-text parsing failures. When the model must return `{contradiction: boolean, reason: string}`, downstream logic becomes deterministic — a lesson we will carry to every LLM pipeline we build.

**User experience matters as much as algorithms (PI toggle, Memory-less)**

The best memory system fails if users don't trust it. Personal Intelligence and Memoryless mode give users explicit control over **what the AI knows and when** — turning memory from a black box into a feature users choose to enable or disable. Lazy session creation, loading spinners, smart auto-scroll, and `@username` labels in the Memory tab showed us that polish and privacy UX score as highly as retrieval accuracy with hackathon judges.

**Iterative development and testing on real infrastructure catches subtle bugs**

Embedding dimension mismatches, regional API endpoints, and Celery workers missing env vars only surfaced when we deployed to real cloud infrastructure and ran the full worker pipeline — not in unit tests or local-only dev. Testing end-to-end on ECS with ApsaraDB and Redis, running Alembic migrations against a live pgvector instance, and re-running the benchmark suite after each module gave us confidence the system works as designed.

---

## What's next for Memoria

**Voice input support**

Extend the chat interface with speech-to-text so users can talk to Memoria hands-free — with the same memory pipeline capturing facts from spoken conversations.

**Multi-agent collaboration via MCP**

Expand MCP skills so multiple specialised agents (planner, researcher, coach) share a unified Personal Memory store, each reading and writing through ownership-checked tools.

**Mobile companion app**

A lightweight mobile client for on-the-go chat and memory review, synced to the same PostgreSQL backend and Redis sessions.

**Enhanced visualisations and memory analytics**

Interactive memory graphs, timeline views, and consolidation/decay dashboards so users can see how their AI's knowledge evolves over weeks and months.

**Fine-tuning Qwen models on personal memory tasks**

Use Memoria's benchmark scenarios and real extraction/consolidation logs to fine-tune Qwen models specifically for memory extraction, conflict detection, and abstractive summarisation — pushing accuracy beyond prompt engineering alone.

---

Track: 1 – MemoryAgent
