# Memoria – Self‑Evolving Personal AI with Human‑like Memory

## System Architecture (v1.1)

Memoria is a self-evolving personal AI with human-like memory. The upgraded
stack (Modules 1–3) adds **MCP memory skills** for external agents, a
**Qwen-Max consolidation engine**, and a **quantitative benchmark suite** that
demonstrates measurable recommendation improvement when memory is present.

## Architecture diagram

```mermaid
graph TD
    %% ── Legend ──────────────────────────────────────────────────────────
    subgraph LEGEND["Legend"]
        direction LR
        L_FE["Frontend layer"]:::frontend
        L_BE["Backend layer"]:::backend
        L_AI["AI / Qwen layer"]:::ai
        L_ST["Storage layer"]:::storage
    end

    %% ── Frontend ─────────────────────────────────────────────────────────
    subgraph FE_LAYER["Frontend layer"]
        BROWSER["User Browser<br/>React / Vite :5173"]
    end

    %% ── Backend ──────────────────────────────────────────────────────────
    subgraph BE_LAYER["Backend layer"]
        API["FastAPI Backend<br/>:8000"]
        MCP["MCP Endpoint<br/>GET /mcp/memory-skills"]
        AGENT["Agent Service<br/>handle_message · PI / MemoryLess labels"]
        RETRIEVE["retrieve_context<br/>Personal Memory · pgvector hybrid search"]
        ARCHIVE_API["Context Archive API<br/>GET /api/search-archive"]
        MCP_TOOLS["Memory Skill Tools<br/>get_core_memories · get_user_preferences<br/>forget_memory · strengthen_memory"]
    end

    %% ── Workers ──────────────────────────────────────────────────────────
    subgraph WORKERS["Celery Workers"]
        BEAT["Celery Beat<br/>scheduler"]
        W_INGEST["Ingestion Worker<br/>extract_and_store_memories"]
        W_DECAY["Decay Worker<br/>apply_decay · daily 03:00 UTC"]
        W_CONSOL["Consolidation Worker<br/>consolidate_memories · weekly Sat 04:00 UTC"]
    end

    %% ── Storage ──────────────────────────────────────────────────────────
    subgraph ST_LAYER["Storage layer"]
        REDIS["Redis<br/>Session Memory · last 10 msgs + Celery broker"]
        PG["PostgreSQL 16 + pgvector<br/>Personal Memory · memories table"]
        ARCHIVE["PostgreSQL chat_messages<br/>Context Archive · full transcripts"]
    end

    %% ── AI / Qwen ────────────────────────────────────────────────────────
    subgraph AI_LAYER["AI / Qwen Cloud (DashScope)"]
        QWEN_PLUS["Qwen-Plus<br/>chat · function calling · structured JSON"]
        QWEN_MAX["Qwen-Max<br/>consolidation · json_schema output"]
        EMBED["text-embedding-v3<br/>memory + query embeddings"]
    end

    %% ── External ───────────────────────────────────────────────────────────
    EXT["External AI Agents<br/>MCP tool callers"]

    %% ── Flow 1: Chat with memory retrieval ───────────────────────────────
    BROWSER -->|"① user message POST /chat"| API
    API --> AGENT
    AGENT -->|"Session Memory history"| REDIS
    AGENT -->|"archive exchange (non-MemoryLess)"| ARCHIVE
    AGENT --> RETRIEVE
    RETRIEVE -->|"Personal Memory · similarity × importance × recency"| PG
    RETRIEVE -->|"query embedding"| EMBED
    API --> ARCHIVE_API
    ARCHIVE_API -->|"on-demand ILIKE search"| ARCHIVE
    AGENT -->|"context + message"| QWEN_PLUS
    QWEN_PLUS -->|"personalized reply"| AGENT
    AGENT --> API
    API --> BROWSER

    %% ── Flow 2: Async memory ingestion ───────────────────────────────────
    AGENT -.->|"enqueue extract_memories_task"| W_INGEST
    W_INGEST -->|"function calling extract_memories"| QWEN_PLUS
    W_INGEST -->|"embed each memory"| EMBED
    W_INGEST -->|"INSERT memories"| PG
    REDIS --- W_INGEST

    %% ── Flow 3: Daily decay ───────────────────────────────────────────────
    BEAT -->|"③ daily trigger"| W_DECAY
    W_DECAY -->|"apply_decay · archive low importance"| PG

    %% ── Flow 4: Weekly consolidation ─────────────────────────────────────
    BEAT -->|"④ weekly trigger"| W_CONSOL
    W_CONSOL -->|"cluster similar memories ≥ 0.75"| PG
    W_CONSOL -->|"summarize cluster"| QWEN_MAX
    W_CONSOL -->|"store summary · mark is_consolidated"| PG

    %% ── Flow 5: MCP interoperability ─────────────────────────────────────
    EXT -->|"⑤ discover tools"| MCP
    MCP --> MCP_TOOLS
    EXT -->|"invoke memory skill"| MCP_TOOLS
    MCP_TOOLS -->|"ownership-checked queries"| PG
    MCP_TOOLS --> EXT

    %% ── Layer colours ────────────────────────────────────────────────────
    classDef frontend fill:#dbeafe,stroke:#1d4ed8,color:#1e3a8a
    classDef backend fill:#ffedd5,stroke:#c2410c,color:#7c2d12
    classDef ai fill:#f3e8ff,stroke:#7e22ce,color:#581c87
    classDef storage fill:#dcfce7,stroke:#15803d,color:#14532d

    class BROWSER,L_FE frontend
    class API,MCP,AGENT,RETRIEVE,ARCHIVE_API,MCP_TOOLS,BEAT,W_INGEST,W_DECAY,W_CONSOL,L_BE backend
    class QWEN_PLUS,QWEN_MAX,EMBED,L_AI ai
    class REDIS,PG,ARCHIVE,L_ST storage
    class EXT frontend
```

### Data flows (numbered in diagram)

| # | Flow | Path |
|---|------|------|
| ① | **Chat with memory** | User message → FastAPI → `retrieve_context` (pgvector similarity) → Qwen-Plus with packed context → personalized response |
| ② | **Memory ingestion** | Chat turn → Celery ingestion worker → Qwen-Plus function calling (`extract_memories`) → `text-embedding-v3` → store in PostgreSQL |
| ③ | **Daily decay** | Celery Beat (03:00 UTC) → `apply_decay` → exponential importance decay → soft-delete (`archived`) low-importance memories |
| ④ | **Weekly consolidation** | Celery Beat (Sat 04:00 UTC) → `consolidate_memories` → cluster by cosine similarity (≥ 0.75) → Qwen-Max summary → link originals via `parent_id` / `is_consolidated` |
| ⑤ | **MCP interoperability** | External agent → `GET /mcp/memory-skills` → invoke tool (`get_core_memories`, etc.) → ownership-checked DB query → JSON result |
| ⑥ | **Context Archive** | Each non-MemoryLess reply → `chat_messages`; explicit recall via `GET /api/search-archive?query=...` (token-guarded) |

## Memory tiers (Level 4)

| Tier | Where | Behaviour |
|------|-------|-----------|
| **Session Memory** | Redis | Last 10 messages of the active chat; always in the model context |
| **Personal Memory** | `memories` table | User-centric facts; extraction, decay, consolidation, conflict resolution |
| **Personal Intelligence** | `users.global_memory_enabled` | ON = all Personal Memories; OFF = current session + manual core memories (no `session_id`) |
| **MemoryLess** | Redis only | No Personal Memory read/write, no archive; PI ignored |
| **Context Archive** | `chat_messages` | Full transcripts; on-demand search only, not routine retrieval |

## Why this architecture

Memoria separates **interactive latency** from **durable memory work**. Chat
requests stay on the FastAPI async path (sub-second retrieval + one Qwen-Plus
call), while ingestion, decay, and consolidation run in Celery workers so heavy
LLM and database operations never block the user. Redis holds ephemeral session
state; PostgreSQL with pgvector is the single source of truth for long-term
memory. This split scales horizontally: add API replicas for traffic and worker
replicas for backlog, without coupling user-facing response time to background
processing volume.

## Key design patterns

**pgvector hybrid retrieval** ranks candidates by cosine similarity multiplied
by importance and a recency decay factor, then greedily packs context under a
token budget—always prioritizing `core` memories first. **Celery background
jobs** decouple write-heavy pipelines (extraction, decay, consolidation) from
the request/response cycle and are scheduled declaratively via Celery Beat.
**MCP memory skills** (Module 1) expose four async tools—`get_core_memories`,
`get_user_preferences`, `forget_memory`, `strengthen_memory`—over a standard
HTTP catalog endpoint, letting external Qwen agents interoperate without
tight coupling to Memoria's chat API. **Structured JSON output** via
`call_qwen_structured()` enforces DashScope `json_schema` responses for
consolidation (`summary` + `key_themes`), reflection (`reflection` + `traits`),
and conflict detection (`contradiction` + `reason`), while ingestion continues
to use function calling. The **benchmark suite** (Module 3) provides
quantitative proof that memory-aware recommendations score higher on accuracy,
safety, and coherence than memory-less baselines.

## Memory lifecycle

1. **Capture** — after each chat turn, the ingestion worker calls Qwen-Plus
   function calling to extract structured memories (`core`, `episodic`,
   `semantic`, `procedural`).
2. **Embed** — each memory is vectorized with `text-embedding-v3` (1024 dims)
   and stored in the `memories` table alongside importance, decay rate, and
   metadata.
3. **Retrieve** — at query time, `retrieve_context` embeds the user message and
   returns the most relevant packed context for Qwen-Plus.
4. **Consolidate** — weekly, similar recent memories are clustered and
   summarized by Qwen-Max into a single semantic memory (structured JSON with
   `summary` and `key_themes`); originals are marked `is_consolidated` and
   linked via `parent_id`.
5. **Decay** — daily, non-core memories lose importance exponentially; those
   falling below the archive threshold are soft-deleted.

## Components reference

| Component | Role |
|-----------|------|
| `frontend/` | React/Vite dashboard — Chat (Markdown), Memory tab with stats cards + type chart |
| `backend/app/main.py` | FastAPI entrypoint — `/health`, `/chat`, `/mcp/memory-skills` |
| `backend/app/mcp/memory_skill.py` | MCP tool implementations for external agents |
| `backend/app/models/chat_message.py` | Context Archive ORM (`chat_messages` table) |
| `backend/app/api/archive.py` | On-demand transcript search (`GET /api/search-archive`) |
| `backend/app/memory/retrieval.py` | Personal Memory retrieval with PI / MemoryLess scoping |
| `backend/app/memory/reflection.py` | Structured user reflection synthesis (`traits` in metadata) |
| `backend/app/memory/conflict_detection.py` | pgvector similarity + structured contradiction checks |
| `backend/app/core/dashscope_client.py` | DashScope helpers incl. `call_qwen_structured()` |
| `scripts/benchmark.py` | Quantitative with/without-memory benchmark (Module 3) |
| `infrastructure/acs_deployment.tf` | Alibaba Cloud IaC (ECS, ApsaraDB PostgreSQL, Redis) |

## Deployment

Infrastructure-as-code for Alibaba Cloud lives in
[`infrastructure/acs_deployment.tf`](../infrastructure/acs_deployment.tf); the
backend container image is defined by [`backend/Dockerfile`](../backend/Dockerfile).
