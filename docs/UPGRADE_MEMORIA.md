# Memoria Upgrade Plan v1.1 (Qwen-Optimized)

**Project:** Memoria – Self-Evolving Personal AI with Human-like Memory  
**Track:** 1 – MemoryAgent  
**Version:** Upgrade Plan v1.1  
**Goal:** Elevate current implementation from ~64/100 to **Winning Level (90+/100)**

---

## Current Repository State (IMPORTANT)

Module 1 (Project Scaffold & Environment Setup) is implemented. The Python backend lives under `backend/`:

- `backend/requirements.txt` — backend dependencies.
- `backend/app/main.py` — FastAPI app exposing `GET /health`.
- `backend/app/config.py` — `pydantic-settings` config; resolves `.env` from the repo root.
- `backend/app/{api,core,memory,services,schemas}/` — package folders, populated by later modules.

**Modules 2–10 (database models, ingestion, retrieval, forgetting, chat API, sessions, dashboard, deployment, tests) are NOT implemented yet.**

### Running the Backend (Dev)

- Create a venv: `python3 -m venv venv && source venv/bin/activate`
- Install deps: `pip install -r backend/requirements.txt`
- Start from `backend/`: `uvicorn app.main:app --reload --port 8000`
- Verify: `curl localhost:8000/health` → `{"status":"ok","service":"memoria","version":"0.1.0"}`
- Swagger UI at `/docs`

### Frontend (`frontend/`)

- Vite + React app. Run: `npm run dev` (port 5173)
- Vite proxies `/chat` and `/api` to backend (port 8000)
- Tabs: **Chat** (`POST /chat`), **Memory** (`GET /api/memories`, `DELETE /api/memories/{id}`)
- Destructive operations require `X-API-Token` header (default `memoria-demo-token`)

### Database & Celery

- **PostgreSQL 16 + pgvector extension** required for DB work
- Default DSN: `postgresql+asyncpg://user:pass@localhost/memoria`
- Run Alembic from `backend/`: `alembic upgrade head`
- **Redis** required for Celery broker: `redis://localhost:6379/0`
- Start worker from `backend/`: `celery -A celery_app worker --loglevel=info`
- Start beat scheduler: `celery -A celery_app beat --loglevel=info`

### DashScope / Qwen Configuration

- Requires `DASHSCOPE_API_KEY` env var (international region key)
- Set endpoint via `DASHSCOPE_BASE_URL` (e.g., `https://dashscope-intl.aliyuncs.com/api/v1`)
- `.env` in repo root is read automatically by `app/config.py`
- Working models: `qwen-plus`, `qwen-max`, `text-embedding-v3`
- Note: `qwen3-plus` may not be available on all accounts; verify first

---

## Executive Summary

This upgraded plan integrates **Qwen Cloud's best capabilities** (Qwen3 series, advanced function calling, long-context reasoning, and MCP) to maximize your score in **Technical Depth** and **Innovation**.

Each module includes **Qwen-specific optimizations** and ready-to-use prompts for Cursor.

**Timeline Recommendation:** Complete Level 1 in 2–3 days.

---

## LEVEL 1: Must-Do Upgrades (Target: +15–18 points)

### Module 1: MCP Integration + Custom Skills (Qwen-Optimized)

**Objective:** Expose Memory as a reusable MCP skill using Qwen's tool calling standards.

**Scoring Impact:** +6–7 points (Technical Depth & Engineering).

**Files to Create/Modify:**
- Create: `backend/app/mcp/__init__.py`
- Create: `backend/app/mcp/memory_skill.py`
- Modify: `backend/app/main.py` (register MCP route)
- Modify: `backend/requirements.txt` (add MCP dependencies if needed)

**Implementation Steps**

1. **Create the MCP module directories:**
   ```bash
   mkdir -p backend/app/mcp
   touch backend/app/mcp/__init__.py
   ```

2. **Generate `memory_skill.py` using Cursor:**

   Paste this prompt into Cursor:
   ```
   I have a working FastAPI backend with a Memory model in PostgreSQL + pgvector 
   and DashScope client for Qwen integration.
   
   Create a production-grade MCP skill server in backend/app/mcp/memory_skill.py 
   using Qwen3 best practices.
   
   Implement these tools:
   
   1. get_core_memories(user_id: str) -> list[dict]
      - Returns memories with importance >= 7 and created_at in last 30 days
      - Format: [{"id": str, "content": str, "importance": int, "created_at": str}]
      - Handle missing user gracefully (return empty list)
   
   2. get_user_preferences(user_id: str) -> dict
      - Extract preferences from top memories (importance >= 8)
      - Return: {"allergies": [], "interests": [], "goals": [], "constraints": []}
      - Return empty structure if no preferences found
   
   3. forget_memory(user_id: str, memory_id: str, reason: str) -> bool
      - Soft-delete: mark memory as deleted with reason
      - Check ownership before deletion
      - Return True on success, False if not found or unauthorized
   
   4. strengthen_memory(user_id: str, memory_id: str) -> bool
      - Increase importance score by 1 (capped at 10)
      - Update updated_at timestamp
      - Return True on success
   
   Requirements:
   - Use existing Memory model and async database session
   - Add proper error handling (try/except with logging)
   - Include permission checks (verify user_id ownership)
   - Make it compatible with Qwen's MCP standard (async functions, clear types)
   - Add docstrings for each tool
   ```

3. **Register MCP endpoint in `backend/app/main.py`:**

   Add this after the `/health` endpoint:
   ```python
   @app.get("/mcp/memory-skills")
   async def memory_skills():
       """Expose memory operations as MCP tools for Qwen."""
       return {
           "tools": [
               {
                   "name": "get_core_memories",
                   "description": "Retrieve important memories for a user (importance >= 7)"
               },
               {
                   "name": "get_user_preferences",
                   "description": "Extract user preferences from memories"
               },
               {
                   "name": "forget_memory",
                   "description": "Soft-delete a memory with reason"
               },
               {
                   "name": "strengthen_memory",
                   "description": "Increase importance of a memory (capped at 10)"
               }
           ]
       }
   ```

**How to Verify**
- Start backend: `cd backend && uvicorn app.main:app --reload --port 8000`
- Test endpoint: `curl localhost:8000/mcp/memory-skills`
- Should return JSON with four tools listed
- (Optional) Call a tool via `curl -X POST localhost:8000/mcp/memory-skills` with sample data

**Scoring Impact**  
+6–7 points (Technical Depth & Engineering; Sophisticated API Use)

---

### Module 2: Advanced Memory Consolidation Engine (Qwen-Optimized)

**Objective:** Use Qwen3-Max for high-quality clustering and abstractive summarization.

**Scoring Impact:** +5–6 points (Innovation & AI Creativity).

**Files to Create/Modify:**
- Create: `backend/app/memory/consolidation.py`
- Modify: `backend/app/memory/models.py` (ensure `parent_id` and `consolidated_at` fields exist)
- Modify: `celery_app/tasks.py` (add consolidation task to Celery Beat)

**Implementation Steps**

1. **Update Memory model:**

   In `backend/app/memory/models.py`, use Cursor to add these fields if missing:
   ```
   Add to the Memory model:
   - parent_id: Optional[str] = None  # Reference to summary memory
   - is_consolidated: bool = False    # True if used in consolidation
   - consolidated_at: Optional[datetime] = None
   
   Add index: db.Index('ix_user_consolidated', 'user_id', 'is_consolidated')
   ```

2. **Create consolidation engine:**

   Paste into Cursor:
   ```
   Create backend/app/memory/consolidation.py with these functions:
   
   async def consolidate_memories(user_id: str) -> int:
       """Consolidate non-core memories using Qwen3-Max clustering."""
       
       Steps:
       1. Fetch non-consolidated memories from past 7 days for user
       2. Use pgvector similarity search to find clusters (similarity > 0.75)
       3. For each cluster with 3+ memories:
          a. Extract core facts (dates, topics, entities)
          b. Call Qwen3-Max with system prompt:
             "You are a master memory consolidator. Synthesize these related memories 
              into ONE concise semantic memory (< 50 words) that captures the essence."
          c. Insert summary memory with importance=8, source='consolidation'
          d. Mark originals: parent_id=summary_id, is_consolidated=True, consolidated_at=now()
       4. Log: "Consolidated N memories for user X into M summaries"
       5. Return count of summaries created
       
       Error handling:
       - If Qwen call fails, log warning and skip cluster
       - If no clusters found, return 0
       - Use proper async/await and db session context
   
   Also create:
   async def get_consolidation_stats(user_id: str) -> dict:
       - Return {"total_memories": int, "consolidated_count": int, "summaries": int}
   ```

3. **Add Celery Beat task in `celery_app/tasks.py`:**

   ```python
   from celery.schedules import crontab
   from celery_app import app as celery_app
   from app.memory.consolidation import consolidate_memories
   
   @celery_app.task(name='consolidate_memories_task')
   def consolidate_memories_task():
       """Run consolidation for all active users (weekly, Sunday 4 AM UTC)."""
       # Fetch users with memories created in last 7 days
       # For each user, call consolidate_memories(user_id) asynchronously
       # Log summary: "Consolidation complete: N users, M total summaries"
   
   # In celery_app/__init__.py or celery.py, add to beat_schedule:
   app.conf.beat_schedule = {
       'consolidate-memories-weekly': {
           'task': 'consolidate_memories_task',
           'schedule': crontab(day_of_week=6, hour=4, minute=0),
       },
   }
   ```

**How to Verify**
- Start Celery worker: `cd backend && celery -A celery_app worker --loglevel=info`
- Manually trigger (optional): `celery -A celery_app call consolidate_memories_task`
- Check PostgreSQL: `SELECT * FROM memory WHERE source='consolidation'`
- Verify `parent_id` links and `is_consolidated` flags set correctly
- Check logs for consolidation progress messages

**Scoring Impact**  
+5–6 points (Innovation & AI Creativity; Memory Management)

---

### Module 3: Benchmark Suite & Quantitative Proof

**Objective:** Demonstrate measurable intelligence growth using Qwen models.

**Scoring Impact:** +4 points (Problem Value & Impact).

**Files to Create:**
- Create: `scripts/benchmark.py`
- Create: `scripts/benchmark_results.json` (output)
- Create: `scripts/benchmark_results.png` (chart output)

**Implementation Steps**

1. **Create the benchmark script:**

   Use Cursor with this prompt:
   ```
   Create scripts/benchmark.py to prove Memoria's memory system improves decision quality.
   
   Benchmark structure:
   
   1. Define a synthetic user profile:
      - Allergies: ["peanuts", "shellfish"]
      - Dietary: vegetarian
      - Interests: ["hiking", "cooking", "machine learning"]
      - Goals: ["eat healthier", "learn Python"]
      - Preferences: likes spicy, dislikes bland, prefers local restaurants
   
   2. Define 12 test scenarios:
      - "Recommend a restaurant for Friday dinner"
      - "Suggest a weekend activity"
      - "What should I cook tonight?"
      - (etc., covering food, activities, learning)
   
   3. Run WITHOUT memory:
      - Call Qwen-Plus with just the scenario (no context)
      - Extract recommendation from response
      - Score: accuracy (0-1), safety (0-1), coherence (0-1)
   
   4. Run WITH memory:
      - Insert user profile as memories into PostgreSQL
      - Call Qwen-Plus with scenario + retrieved memories context
      - Extract recommendation
      - Score using same metrics
   
   5. Measure & output:
      - Print markdown table: Scenario | Without (A/S/C) | With (A/S/C) | Improvement %
      - Calculate average improvement %
      - Save JSON: {"scenarios": [...], "avg_accuracy": 0.XX, "avg_improvement": XX}
      - Generate matplotlib bar chart comparing before/after scores
      - Save chart as PNG: scripts/benchmark_results.png
   
   Notes:
   - Use asyncio for Qwen calls
   - Handle failures gracefully (skip failed scenarios, log warnings)
   - Aim for 20-40% improvement to show real value
   ```

2. **Run the benchmark:**
   ```bash
   cd backend
   python ../scripts/benchmark.py
   ```

**How to Verify**
- Script runs without errors
- Output includes markdown table with results
- JSON file created: `scripts/benchmark_results.json`
- Chart generated: `scripts/benchmark_results.png`
- Average improvement should be 20–40% for a good system

**Scoring Impact**  
+4 points (Problem Value & Impact; Measurable Proof)

---

### Module 4: Professional Architecture Diagram (Qwen-Centric)

**Objective:** Create a clear, judge-friendly visual showing Qwen integration.

**Files to Create:**
- Create: `docs/ARCHITECTURE.md`

**Implementation Steps**

1. **Create the architecture document:**

   Use Cursor with this prompt:
   ```
   Create docs/ARCHITECTURE.md with a professional Mermaid diagram for Memoria.
   
   Include these components:
   - Frontend (React/Vite, port 5173)
   - FastAPI Backend (port 8000)
   - Redis (session store + Celery broker)
   - PostgreSQL 16 + pgvector (multi-layer memory store)
   - Celery Workers (ingestion, decay, consolidation using Qwen3-Max)
   - DashScope/Qwen Cloud services:
     * Qwen3-Plus (chat, function calling)
     * Qwen3-Max (consolidation, summaries)
     * text-embedding-v3 (memory embeddings)
     * MCP Skills (memory operations)
   - External agents → MCP memory skills
   
   Data flows:
   1. User message → Backend
   2. Backend retrieves similar memories (pgvector)
   3. Sends to Qwen3-Plus with context
   4. Qwen returns response + tool calls
   5. Backend executes tools, stores new memories
   6. Weekly: consolidation task uses Qwen3-Max
   
   Use Mermaid graph syntax with clear labels.
   Below the diagram, add 2–3 paragraphs explaining:
   - Why this architecture (scalability, separation of concerns)
   - Key design patterns (async/await, pgvector similarity, Celery background jobs)
   - How memory lifecycle works (capture → embed → consolidate → decay)
   ```

2. **Verify the diagram renders:**
   - View `docs/ARCHITECTURE.md` on GitHub or locally
   - Mermaid diagram should display cleanly
   - Text explanation is clear and comprehensive

**Scoring Impact**  
+2–3 points (Technical Communication; Design Clarity)

---

## LEVEL 2: Strong Differentiators (Next Phase)

After completing Level 1, these modules add sophistication:

### 2.1 Memory Conflict Detection & Versioning

**Objective:** Handle contradictory memories intelligently.

**Impact:** +3–4 points (AI Creativity, Safety)

**Quick Implementation:**
- On memory insertion, query for contradictions (opposite assertions about same entity)
- If found, mark old as `superseded=True` and link `version_id`
- Log conflicts for auditing

**File:** `backend/app/memory/conflict_detection.py`

---

### 2.2 Reflective Memory Layer

**Objective:** AI analyzes its own knowledge about the user.

**Impact:** +3–4 points (Innovation)

**Quick Implementation:**
- Every N conversations, Qwen reflects on what it knows
- Example: "Based on my memories, this user values efficiency"
- Use reflection to improve future responses

**File:** `backend/app/memory/reflection.py`

---

### 2.3 User Feedback Loop

**Objective:** Thumbs up/down improves memory importance.

**Impact:** +3–4 points (UX, Learning)

**Quick Implementation:**
- Add feedback buttons to chat responses
- Positive feedback → increase importance of related memories
- Negative feedback → decrease importance

**Files:** `frontend/src/components/Chat.jsx`, `backend/app/api/memories.py`

---

### 2.4 Structured Output (DashScope JSON Schema)

**Objective:** Enforce strict JSON from Qwen across consolidation, reflection, and conflict detection.

**Impact:** +2–3 points (Technical Depth; Reliability)

**Files to Create/Modify:**
- Modify: `backend/app/core/dashscope_client.py` — add `call_qwen_structured()`
- Modify: `backend/app/memory/consolidation.py` — structured summary + `key_themes`
- Modify: `backend/app/memory/reflection.py` — structured reflection + `traits`
- Modify: `backend/app/memory/conflict_detection.py` — structured `contradiction` boolean
- Do **not** change `ingestion.py` (function calling is already structured)

**Implementation:**
- `call_qwen_structured(messages, json_schema, model="qwen-plus")` uses DashScope
  `result_format="json"` with `json_schema` and the international base URL.
- **Consolidation schema:** `{summary: string, key_themes: string[]}` — store summary
  as content, themes in metadata.
- **Reflection schema:** `{reflection: string, traits: string[]}` — store reflection
  as content, traits in metadata.
- **Conflict schema:** `{contradiction: boolean, reason: string}` — use boolean
  for conflict decisions.

**How to Verify**
- Run consolidation on a user with 3+ similar memories; check metadata has `key_themes`.
- Trigger reflection (10th session message); check metadata has `traits`.
- Insert contradictory facts; confirm conflict detection logs structured `reason`.

---

## LEVEL 3: Final Polish

### 3.1 Enhanced Dashboard & Visualizations

**Objective:** Upgrade the Memory tab with aggregate statistics and a type distribution chart.

**Files to Modify:**
- `backend/app/api/memories.py` — add `GET /api/memory-stats`
- `frontend/src/components/MemoryGraph.jsx` — stats cards + horizontal bar chart
- `frontend/src/index.css` — dark-theme styling for stats panel

**Backend (`GET /api/memory-stats?user_id=...`):**
- Requires `X-API-Token` header (same demo token as destructive ops).
- Returns:
  ```json
  {
    "total_memories": 12,
    "consolidated_count": 3,
    "summaries_count": 1,
    "avg_importance": 0.82,
    "last_consolidation": "2026-07-11T10:00:00Z",
    "types": { "core": 2, "episodic": 4, "semantic": 5, "procedural": 1 }
  }
  ```
- Queries: active (non-archived) memories; `is_consolidated=True`; `metadata.source='consolidation'`; `AVG(importance)`; `MAX(consolidated_at)`; counts per `type`.

**Frontend:**
- Stats section above the memory table with cards for totals, consolidation, summaries, avg importance, last consolidation.
- CSS-based horizontal bar chart for memory type distribution (no extra chart library).
- Refresh reloads both `/api/memories` and `/api/memory-stats`.

**How to Verify**
- Seed a few memories for a user, open the Memory tab, click Refresh.
- Stats cards and type bars should match the database counts.

### 3.2 Demo Video Script & Recording

3-minute walkthrough: setup → chat → memory retrieval → consolidation.

### 3.3 Final README & Blog Post

Strong feature highlights, architecture overview, deployment instructions.

### 3.4 Chat Markdown Rendering

**Objective:** Render Qwen's Markdown-formatted chat replies in the frontend.

**Files to Modify:**
- `frontend/package.json` — add `react-markdown`
- `frontend/src/components/Chat.jsx` — wrap assistant messages in `<ReactMarkdown>`
- `frontend/src/index.css` — style lists, code blocks, and paragraphs inside bubbles

**Implementation:**
- Install: `cd frontend && npm install react-markdown`
- For `role === 'assistant'`, render `message.content` via `<ReactMarkdown>` inside the
  existing bubble styling.
- Add `.markdown-content` CSS so bold, italic, lists, and code inherit bubble colors.

**How to Verify**
- Rebuild: `cd frontend && npm run build`
- Send: "Give me a spicy vegetarian recipe with steps"
- Reply should show formatted **bold**, *italic*, and bullet lists—not raw `**` symbols.

---

## Level 3.5 – UI/UX Polish

**Objective:** Make the Memoria demo more intuitive and judge-friendly.

**Completed items:**

1. **Removed guest mode** — Login/signup is required; the “Continue as guest (manual user ID)” flow was removed from `Auth.jsx` and `App.jsx`.
2. **Lazy session creation** — “+ New Chat” uses a client-side UUID until the first message is sent; the backend creates the persistent session atomically in `POST /chat` via `ensure_session_exists()`. Empty chats no longer appear in the sidebar (`GET /sessions` filters sessions with messages).
3. **Personal Intelligence in sidebar** — The PI toggle moved from the header to the sidebar (below New Chat), with a descriptive tooltip; still backed by `GET/PATCH /auth/preferences`.
4. **New Memoryless Chat button** — Replaced the MemoryLess checkbox with a “🕶️ Memoryless” sidebar button and confirmation modal; memoryless sessions show a distinct badge in the list.
5. **Loading & empty states** — Spinners on auth submit, persona save, chat send, and sidebar actions; Memory tab shows “No memories in this chat yet.” when the current chat has none; consistent “No chats yet” sidebar empty state.
6. **Landing page** — `Landing.jsx` shows project highlights and benchmark summary before login; “Launch App” opens the auth screen.

**Files touched:** `frontend/src/App.jsx`, `Auth.jsx`, `Sidebar.jsx`, `Chat.jsx`, `Landing.jsx`, `MemoryGraph.jsx`, `Persona.jsx`, `index.css`; `backend/app/api/sessions.py`, `chat.py`, `memories.py`; `backend/app/services/agent_service.py`.

---

## Level 3.6 – UI Glitch Fixes

**Objective:** Fix visible polish issues in the deployed dashboard.

**Completed items:**

1. **Memory tab user label** — The memory count line now shows `@username` when logged in (e.g. `0 memories for @awais`) instead of the raw UUID; falls back to `user_id` if username is unavailable.
2. **Markdown line breaks** — Assistant replies preprocess `<br>` / `&lt;br&gt;` tags into newlines before `ReactMarkdown` rendering (no raw HTML plugin required).
3. **Smart auto-scroll** — Chat scrolls smoothly to new messages only when the user is already near the bottom (50px threshold); a floating “scroll to bottom” button appears when reading older messages. Thin, subtle scrollbar styling on the chat container.

**Files touched:** `frontend/src/components/MemoryGraph.jsx`, `Chat.jsx`, `App.jsx`, `index.css`.

---

## Level 3.7 – LaTeX / Math Rendering

**Objective:** Render mathematical equations in assistant chat replies (inline `$...$` and block `$$...$$`).

**Implementation:**
- Added `remark-math`, `rehype-katex`, and `katex` to the frontend.
- `Chat.jsx` passes `remarkMath` + `rehypeKatex` to `ReactMarkdown` and imports KaTeX CSS.
- Preprocessing fixes common Qwen LaTeX typos (e.g. `,dx` → `\,dx`) and tightens spaced delimiters (`$ f(x) $` → `$f(x)$`).
- Dark-theme overflow styling for display equations in `.markdown-content`.

**How to verify:** Ask for a calculus or trig derivation; equations should render as formatted math, not raw `$...$` text.

**Files touched:** `frontend/package.json`, `Chat.jsx`, `index.css`.

---

## Level 4 – Context-Aware Memory Layering

**Objective:** Re-architect Memoria into distinct, hackathon-optimised memory tiers with clear naming and strict isolation rules.

### Tier definitions

| Tier | Storage | Purpose |
|------|---------|---------|
| **Session Memory** | Redis (last 10 messages) | Short-term context for the active chat; always passed to the model |
| **Personal Memory** | PostgreSQL `memories` + pgvector | User-centric facts (preferences, identity, goals); importance, decay, consolidation, conflict resolution |
| **Personal Intelligence (PI)** | User preference `global_memory_enabled` | When ON, retrieve all Personal Memories across sessions; when OFF, only current-session memories + essential facts (`importance >= 0.9`) |
| **MemoryLess** | Redis only while open | `is_memoryless=True` sessions: no Personal Memory read/write, no Context Archive, PI disabled |
| **Context Archive** | PostgreSQL `chat_messages` | Full transcripts for non-MemoryLess sessions; queried on demand via `GET /api/search-archive` only |

### Implementation summary

1. **User-centric extraction** — `ingestion.py` system prompt extracts only user-specific facts; Celery receives the user's message only (not the assistant reply).
2. **Context Archive** — `ChatMessage` model + Alembic migration; `agent_service.py` archives each exchange after reply (skips MemoryLess); `GET /api/search-archive` with `X-API-Token`.
3. **PI enforcement** — `retrieval.py` scopes Personal Memory by `is_memoryless` / `global_memory_enabled`; system prompt labels PI ON/OFF/MemoryLess in `agent_service.py`.
4. **MemoryLess isolation** — No extraction, archive, reflection, or cross-session retrieval; frontend banner + disabled PI toggle.

**Files:** `backend/app/memory/ingestion.py`, `retrieval.py`, `services/agent_service.py`, `models/chat_message.py`, `api/archive.py`, `alembic/versions/a7b8c9d0e1f2_*`; `frontend/src/components/Sidebar.jsx`, `Chat.jsx`.

---

## Final Submission Checklist

Before submitting, ensure:

- [ ] **Level 1 Complete**
  - [ ] MCP server deployed and callable from Qwen
  - [ ] Consolidation task runs weekly, summaries stored
  - [ ] Benchmark results show 20%+ improvement
  - [ ] Architecture diagram in docs/ARCHITECTURE.md

- [ ] **Repository & Deployment**
  - [ ] Public GitHub repo with Apache 2.0 license
  - [ ] `infrastructure/acs_deployment.tf` visible and documented
  - [ ] `.gitignore` includes `.env`

- [ ] **Documentation**
  - [ ] README highlights memory features and Qwen integration
  - [ ] AGENTS.md explains agent architecture
  - [ ] Architecture diagram is clear and professional

- [ ] **Demo & Proof**
  - [ ] Benchmark results documented in README
  - [ ] MCP skills demonstrated working
  - [ ] At least one video demo (optional but encouraged)

- [ ] **Code Quality**
  - [ ] No debug prints or TODOs
  - [ ] Error handling throughout
  - [ ] Logging in place for debugging

---

## How to Use This Document

### For Immediate Completion (Next 2–3 Days)

1. **Start with Module 1 (MCP Integration)**
   - Copy the prompt under "Implementation Steps → Step 2"
   - Paste into Cursor
   - Create files and verify endpoint works
   
2. **Then Module 2 (Consolidation)**
   - Create consolidation module
   - Set up Celery Beat task
   - Manually trigger to verify

3. **Then Module 3 (Benchmark)**
   - Run benchmark script
   - Save results

4. **Finally Module 4 (Architecture)**
   - Create diagram
   - Commit all changes

### For Longer Timeline

- Complete Level 1 first (2–3 days)
- Implement Level 2 modules (3–5 days)
- Final polish and demo (1–2 days)

---

## Key Success Factors

1. **Clear, working code** — Finish each module completely before moving on
2. **Proper error handling** — Robust, production-ready
3. **Documentation** — Judges should understand architecture without asking
4. **Measurable proof** — Benchmarks and logs provide confidence
5. **Iterative improvement** — Start Level 1; expand based on feedback

---

## Troubleshooting

**"My Qwen API call fails"**  
Check `DASHSCOPE_API_KEY` is set and `DASHSCOPE_BASE_URL` is correct (international endpoint). Both in `.env`.

**"Consolidation task doesn't run"**  
Ensure Redis is running and Celery Beat is active. Check logs for scheduling errors.

**"Benchmark takes too long"**  
Reduce scenarios from 12 to 6 or increase Qwen timeout.

**"Where do I paste the prompt?"**  
Create a new file in the repo, then paste the prompt into Cursor's AI chat (Cmd+K on Mac, Ctrl+K on Windows).

---

**Ready to start?**  
Begin with **Module 1** and follow the steps in order. Good luck! 🚀
