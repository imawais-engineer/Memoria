"""Static product knowledge injected into the chat agent system prompt.

Gives Memoria's AI accurate answers about architecture, features, and behaviour
when users ask how the app works. Synthesized from docs/ and the implementation.
"""

MEMORIA_KNOWLEDGE_BASE = """
## Memoria product knowledge base

Use this reference when users ask how Memoria works, its architecture, features,
implementation, or capabilities. Answer in clear, user-friendly language.

### What Memoria is
Memoria is a Self‑Evolving Personal AI with Human‑like Memory — a MemoryAgent
built on Qwen Cloud (Alibaba DashScope). It remembers user preferences, goals,
and identity across chat sessions, forgets stale facts, resolves conflicts, and
reflects on patterns over time.

### Tech stack
- **Frontend:** React + Vite dashboard (port 5173) — Chat, Memories, Persona,
  Tasks, Media, Settings, Help, About. Landing at `/`, auth at `/auth`, app at `/app`.
- **Backend:** Python 3.12 + FastAPI (port 8000) — async API, Swagger at `/docs`.
- **LLM:** Qwen models via DashScope (`qwen-plus`, `qwen-max`, `qwq-plus`,
  `qwen-turbo` selectable in chat).
- **Embeddings:** `text-embedding-v3` (1024 dimensions).
- **Session store:** Redis — last 10 messages per chat, 7-day TTL.
- **Long-term memory:** PostgreSQL 16 + pgvector (`memories` table).
- **Context archive:** PostgreSQL `chat_messages` — full transcripts.
- **Background jobs:** Celery + Redis broker — ingestion, decay, consolidation.
- **MCP:** `GET /mcp/memory-skills` exposes memory tools for external agents.

### Project structure (backend)
- `backend/app/main.py` — FastAPI entry, routers, `/health`, MCP catalog.
- `backend/app/services/agent_service.py` — chat orchestration, system prompt.
- `backend/app/memory/` — ingestion, retrieval, forgetting, consolidation,
  conflict detection, reflection.
- `backend/app/api/` — chat, sessions, memories, tasks, generate, auth, feedback.
- `backend/celery_app/` — workers and Beat schedules.
- `frontend/src/components/` — Chat, Sidebar, MemoryGraph, MediaPage, TasksPage, etc.

### Memory tiers
| Tier | Storage | Behaviour |
|------|---------|-----------|
| Session Memory | Redis | Last 10 messages; always in model context |
| Personal Memory | `memories` table | Extracted facts; vector search + decay |
| Personal Intelligence (PI) | `users.global_memory_enabled` | ON = all memories; OFF = current session + core memories without session_id |
| MemoryLess | Redis only | No read/write of personal memory; no archive; media slash commands disabled |
| Context Archive | `chat_messages` | Full transcripts; on-demand search via `GET /api/search-archive` |

### Memory types
`core`, `episodic`, `semantic`, `procedural`, `goal`, `preference`.
Core memories never decay. Goal and preference use decay rate 0.01.

### Memory lifecycle
1. **Capture** — after each non-MemoryLess chat turn, Celery runs Qwen function
   calling (`extract_memories`) on the user message.
2. **Embed & store** — each fact is embedded and saved with importance, decay rate,
   optional `session_id`, and metadata.
3. **Retrieve** — at query time, hybrid ranking: cosine similarity × importance ×
   recency decay; `core` memories packed first under a token budget (~6000).
4. **Conflict detection** — contradictory new facts boost importance and supersede
   older memories automatically.
5. **Consolidation** — weekly (Sun 04:00 UTC): cluster similar memories (≥0.75),
   Qwen-Max summarizes into semantic memories; originals marked consolidated.
6. **Decay** — daily (03:00 UTC): non-core memories lose importance; low scores
   are archived (soft-deleted).
7. **Reflection** — every 10th user message triggers background synthesis of
   higher-level user traits injected into the system prompt.

### Chat flow
1. User sends message → `POST /chat` or `POST /chat/stream` (SSE streaming).
2. Agent loads Redis session history, retrieves personal memories (scoped by PI /
   MemoryLess), applies persona, calls Qwen.
3. Reply returned; exchange archived to `chat_messages` (unless MemoryLess).
4. Memory extraction enqueued to Celery asynchronously.

### Slash commands (chat)
| Command | What it does | Cost |
|---------|--------------|------|
| `/` | Show formatted command help table | Free |
| `/imagine <prompt>` | Generate image (`wan2.1-t2i-plus`) | AI quota |
| `/gen_video <prompt>` | Generate video (`wan2.1-t2v-turbo`) | AI quota |
| `/gen_voice <prompt>` | Voice overview of session (Qwen + TTS) | AI quota |
| `/memorize <fact>` | Manually store a core memory | Free |
| `/create_task <title>` | Create a pending task | Free |
| `/tasks_list` | List pending tasks (numbered 01, 02, …) | Free |
| `/task_complete <ID>` | Mark task complete | Free |
| `/list_memory` | List memories — all user memories when PI ON; current chat only when PI OFF | Free |
| `/forget_memory <ID|ALL>` | Delete memory by list ID or clear scoped set | Free |

### Frontend pages (sidebar)
- **Chat** — main conversation with model switcher and Personal Intelligence toggle.
- **Memories** — stats cards, type bar chart, memory table with Forget actions.
- **Persona** — response length, tone, behaviour traits (injected into system prompt).
- **Tasks** — all tasks (pending first); create via `/create_task` in chat.
- **Media** — generated images/videos; download or permanently delete per asset.
- **Settings** — default model, PI toggle, persona.
- Profile menu: Settings, Help, Feedback, About, Logout.

### Key API endpoints
- `GET /health` — liveness probe.
- `POST /chat`, `POST /chat/stream` — chat (supports `model`, `session_id`, `is_memoryless`).
- `GET/POST/PATCH/DELETE /api/sessions` — session CRUD and titles.
- `GET /api/memories`, `GET /api/memory-stats`, `DELETE /api/memories/{id}` — memory dashboard.
- `POST /api/memorize` — manual memory insert.
- `GET/POST/PATCH/DELETE /api/tasks` — task management.
- `POST /api/generate/image|video|voice`, `GET/DELETE /api/generate/assets` — media.
- `POST /api/feedback` — thumbs up/down strengthens or weakens cited memories.
- `GET /mcp/memory-skills` — MCP tool catalog for external agents.

### MCP memory tools (external agents)
`get_core_memories`, `get_user_preferences`, `forget_memory`, `strengthen_memory` —
ownership-checked, callable without the chat API.

### Usage quotas (per user, configurable on user record)
Default limits: 10 chat messages, 5 images, 2 videos, 2 voice generations.
HTTP 429 when exceeded. Media generation disabled in MemoryLess sessions.

### Authentication
Signup/login with username + favorite book (no email). All data scoped by `user_id`.

### Design principles
- Interactive chat stays fast (async FastAPI + one Qwen call); heavy work in Celery.
- PostgreSQL + pgvector is the source of truth for long-term memory.
- Redis holds ephemeral session state only.
- Personal Intelligence and MemoryLess give users explicit control over memory scope.
""".strip()
