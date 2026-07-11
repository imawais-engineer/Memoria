# Memoria Upgrade Plan v1.0

**Project:** Memoria – Self-Evolving Personal AI with Human-like Memory  
**Current Level:** ~64/100  
**Target Level:** Winning (88–94/100)  
**Estimated Timeline:** 2–3 days for Level 1

---

## Overview

This guide breaks down the path from a functional prototype to a competitive submission into four clear levels. Each module focuses on a specific capability gap and includes concrete files to create, actionable steps, and verification methods.

**The structure is designed for Cursor/IDE workflows:** copy the prompt for each module directly into your AI IDE and follow the implementation steps in order.

---

## LEVEL 1: Core Upgrades (Target: +12–15 Points)

Level 1 addresses the highest-impact improvements: exposing capabilities as reusable services, automating memory consolidation, proving value through benchmarks, and documenting architecture.

### 1.1 MCP Integration & Custom Skills

**Why This Matters**  
Right now, Memoria's memory engine runs only for chat. By exposing it as a Model Context Protocol (MCP) server with custom tools, you:
- Allow Qwen to access memory directly for tasks outside chat
- Demonstrate "sophisticated QwenCloud API use"
- Create a foundation for multi-agent scenarios

**What to Build**  
A lightweight MCP skill server that exposes four tools:
1. `get_core_memories(user_id)` — Returns high-priority memories
2. `get_user_preferences(user_id)` — Structured user preferences
3. `forget_memory(user_id, memory_id, reason)` — Deliberately delete a memory
4. `strengthen_memory(user_id, memory_id)` — Mark memory as important

**Files to Create/Modify**
- Create: `backend/app/mcp/memory_skill.py` (new MCP server)
- Modify: `backend/app/main.py` (register MCP route)
- Modify: `backend/requirements.txt` (add any MCP dependencies)

**Implementation Steps**

1. **Create the MCP server module:**
   ```bash
   mkdir -p backend/app/mcp
   touch backend/app/mcp/__init__.py
   touch backend/app/mcp/memory_skill.py
   ```

2. **Use Cursor/IDE to generate `memory_skill.py`:**
   
   Paste this prompt into Cursor:
   ```
   I have a working FastAPI backend with a Memory model in PostgreSQL + pgvector.
   
   Create a complete MCP skill server in backend/app/mcp/memory_skill.py that exposes
   the following tools for Qwen to call:
   
   1. get_core_memories(user_id: str) -> list[dict]
      - Returns memories with importance >= 7 and created_at in last 30 days
      - Format: {"id", "content", "importance", "created_at"}
      - Handle missing user gracefully (return empty list)
   
   2. get_user_preferences(user_id: str) -> dict
      - Extract preferences from user's top memories (importance >= 8)
      - Return structure: {"allergies": [], "interests": [], "goals": [], "constraints": []}
      - If no preferences found, return empty structure
   
   3. forget_memory(user_id: str, memory_id: str, reason: str) -> bool
      - Soft-delete: mark memory as deleted with the reason
      - Check ownership before deletion
      - Return True on success, False if memory not found or unauthorized
   
   4. strengthen_memory(user_id: str, memory_id: str) -> bool
      - Increase importance score by 1 (capped at 10)
      - Update updated_at timestamp
      - Return True on success
   
   Use the existing Memory model and Database session. Include:
   - Proper error handling (try/except with logging)
   - Permission checks (verify user_id ownership)
   - Graceful degradation (don't crash on edge cases)
   
   Make it compatible with Qwen's MCP standard (async functions, clear return types).
   ```

3. **Register the MCP server in `backend/app/main.py`:**
   
   Add a new route after the `/health` endpoint:
   ```python
   @app.get("/mcp/memory-skills")
   async def memory_skills():
       """Expose memory operations as MCP tools."""
       return {
           "tools": [
               {"name": "get_core_memories", "description": "Retrieve important memories for a user"},
               {"name": "get_user_preferences", "description": "Extract user preferences from memories"},
               {"name": "forget_memory", "description": "Soft-delete a memory with reason"},
               {"name": "strengthen_memory", "description": "Increase importance of a memory"}
           ]
       }
   ```

4. **Update `backend/requirements.txt`** if your IDE suggests MCP dependencies (some projects use `mcp`, `anthropic-mcp`, etc.).

**How to Verify**
- Start the backend: `cd backend && uvicorn app.main:app --reload --port 8000`
- Test the endpoint: `curl localhost:8000/mcp/memory-skills`
- You should see a JSON response with the four tools listed
- (Optional) Call a tool via POST to ensure it works with sample data

**Scoring Impact**  
+5–6 points (Technical Depth & Engineering; Sophisticated API Use)

---

### 1.2 Advanced Memory Consolidation Engine

**Why This Matters**  
Humans don't remember every detail—they abstract patterns. A consolidation system mimics this by clustering similar memories and generating summaries. This proves your system has "sophisticated memory management" beyond basic storage.

**What to Build**  
A weekly task that:
1. Finds memories from the last 7 days
2. Groups similar memories (using pgvector similarity)
3. Summarizes each group with Qwen-Max
4. Stores the summary as a new high-importance memory
5. Marks originals as "consolidated"

**Files to Create/Modify**
- Create: `backend/app/memory/consolidation.py`
- Modify: `backend/app/memory/models.py` (ensure `parent_id` and `is_consolidated` fields exist)
- Modify: `celery_app/tasks.py` (add consolidation task to Celery Beat schedule)

**Implementation Steps**

1. **Add fields to the Memory model:**
   
   Use Cursor to update `backend/app/memory/models.py`:
   ```
   In backend/app/memory/models.py, add these fields to the Memory model if missing:
   
   - parent_id: Optional[UUID] = None  # Reference to the summary memory this was consolidated into
   - is_consolidated: bool = False     # True if this memory was used in a consolidation
   
   Add a db.Index for efficient queries: db.Index('ix_user_consolidated', 'user_id', 'is_consolidated')
   ```

2. **Create the consolidation engine:**
   
   Paste this into Cursor:
   ```
   Create backend/app/memory/consolidation.py with an async function consolidate_memories(user_id: str).
   
   Steps:
   1. Fetch non-consolidated memories from the past 7 days for the user
   2. Use pgvector distance queries to find clusters:
      - Threshold: similarity score > 0.8 (adjust as needed)
      - Group memories with similar embeddings
   3. For each cluster with 3+ memories:
      - Extract core facts from the cluster (dates, topics, names)
      - Call Qwen-Max (qwen-max model) with the cluster to generate a semantic summary
      - Prompt: "Summarize these {count} related memories into a single concise fact that a personal AI should remember. Keep it under 50 words."
      - Insert the summary as a new Memory with importance=8, source='consolidation'
      - Mark original memories: parent_id = summary_id, is_consolidated = True
   4. Log progress (e.g., "Consolidated 12 memories into 3 summaries for user X")
   5. Return count of summaries created
   
   Handle errors gracefully:
   - If Qwen call fails, skip that cluster and log warning
   - If no clusters found, return 0 (no error)
   - Use asyncio and db session properly for async context
   ```

3. **Add Celery Beat task:**
   
   In `celery_app/tasks.py`, add:
   ```python
   from celery.schedules import crontab
   from celery_app import app as celery_app
   
   @celery_app.task(name='consolidate_memories_task')
   def consolidate_memories_task():
       """Run consolidation for all active users (weekly)."""
       # Fetch list of active users (users with memories in last 7 days)
       # For each user, call consolidate_memories(user_id)
       # Log summary: "Consolidated memories for N users"
   
   # Add to beat schedule in celery_app/__init__.py or celery.py:
   app.conf.beat_schedule = {
       'consolidate-memories-weekly': {
           'task': 'consolidate_memories_task',
           'schedule': crontab(day_of_week=6, hour=4, minute=0),  # Sunday 4 AM UTC
       },
   }
   ```

**How to Verify**
- Start a Celery worker: `cd backend && celery -A celery_app worker --loglevel=info`
- (Optional) Manually trigger: `python -c "from celery_app.tasks import consolidate_memories_task; consolidate_memories_task.delay()"`
- Check PostgreSQL: Query the Memory table for records with `source='consolidation'` and verify `parent_id` values
- Check logs for "Consolidated X memories" messages

**Scoring Impact**  
+4–5 points (Innovation & AI Creativity; Memory Management)

---

### 1.3 Benchmark Suite

**Why This Matters**  
Judges want proof that Memoria actually improves decision quality. A benchmark shows:
- Quantifiable improvement (e.g., "89% accuracy vs. 62%")
- Rigorous testing (you understand your own system)
- Real value (not just a proof-of-concept)

**What to Build**  
A standalone script that:
1. Simulates a user profile (allergies, preferences, goals)
2. Runs 12 conversation turns **without** memory
3. Runs the same turns **with** memory
4. Measures three metrics: accuracy, safety compliance, coherence
5. Outputs a comparison table and chart

**Files to Create**
- Create: `scripts/benchmark.py`
- Create: `scripts/benchmark_results.json` (output)

**Implementation Steps**

1. **Create the benchmark script:**
   
   Use Cursor with this prompt:
   ```
   Create scripts/benchmark.py to prove Memoria's memory system improves decision quality.
   
   Benchmark structure:
   1. Define a synthetic user profile:
      - Allergies: ["nuts", "shellfish"]
      - Dietary restrictions: vegetarian
      - Interests: hiking, cooking, machine learning
      - Goal: eat healthier
      - Past decision: liked spicy food, dislikes bland food
   
   2. Define 12 test scenarios (e.g., "Recommend a restaurant for dinner", "Suggest a weekend activity", etc.)
   
   3. Run WITHOUT memory:
      - Call Qwen (qwen-plus) with just scenario, no memory context
      - Extract recommendation from response
      - Score accuracy: Did it respect allergies? (0-1)
      - Score safety: No shellfish recommended? (0-1)
      - Score coherence: Aligns with stated interests? (0-1)
   
   4. Run WITH memory:
      - Insert the user profile as memories into PostgreSQL
      - Call Qwen with scenario + retrieved memories context
      - Extract recommendation
      - Score the same three metrics
   
   5. Generate output:
      - Print a table: Scenario | Without Memory (Acc/Safe/Coh) | With Memory (Acc/Safe/Coh) | Improvement %
      - Calculate average improvement across all scenarios
      - Save results as JSON: {"scenarios": [...], "avg_accuracy": 0.XX, "improvement_pct": XX}
      - Generate a bar chart (matplotlib): scenarios on X-axis, metric scores on Y-axis (two bars per scenario)
   
   Notes:
   - Use asyncio for Qwen calls
   - Handle failures gracefully (skip scenario if Qwen times out)
   - Store benchmark results as JSON for documentation
   - Chart should be saved as PNG in scripts/benchmark_results.png
   ```

2. **Run the benchmark:**
   ```bash
   cd backend
   python ../scripts/benchmark.py
   ```

**How to Verify**
- Script completes without errors
- Output includes a markdown table with results
- JSON file is created: `scripts/benchmark_results.json`
- Chart is generated: `scripts/benchmark_results.png`
- Average improvement should be 15–30% for a functional system

**Scoring Impact**  
+3–4 points (Problem Value & Impact; Measurable Proof)

---

### 1.4 Architecture Diagram

**Why This Matters**  
A clear visual of your system demonstrates:
- You understand your own design
- Judges can quickly grasp how components interact
- Professional presentation

**What to Build**  
A Mermaid diagram + textual explanation showing:
- Frontend (React)
- FastAPI backend
- MCP skill exposure
- Memory pipeline (ingestion → embedding → storage → retrieval)
- External services (Qwen, Redis, PostgreSQL)

**Files to Create/Modify**
- Create: `docs/ARCHITECTURE.md`

**Implementation Steps**

1. **Create the architecture document:**
   
   Use Cursor with this prompt:
   ```
   Create docs/ARCHITECTURE.md with a professional Mermaid architecture diagram for Memoria.
   
   Include:
   - Component boxes: Frontend (React/Vite), FastAPI Backend, Redis (session/broker), 
     PostgreSQL + pgvector (memory store), Celery Workers, DashScope/Qwen Cloud
   - Data flows: User message → Backend → Qwen (embed + generate) → Memory store
   - A separate flow for consolidation: Daily decay task, weekly consolidation task
   - MCP endpoint showing memory-skills exposure
   - Chat flow: 1) Retrieve similar memories from pgvector, 2) Send to Qwen with context, 
     3) Extract tool calls, 4) Execute tools, 5) Store new memories
   
   Use Mermaid graph syntax. Include a legend.
   Below the diagram, add 2–3 paragraphs explaining:
   - Why this architecture was chosen (scalability, separation of concerns)
   - Key design patterns (async/await, pgvector similarity search, Celery for background jobs)
   - How it handles user memory lifecycle (capture → embedding → consolidation → decay)
   ```

2. **Verify the diagram renders:**
   - Open `docs/ARCHITECTURE.md` in GitHub or a Markdown viewer
   - The Mermaid diagram should display cleanly

**Scoring Impact**  
+2–3 points (Technical Communication; Design Clarity)

---

## LEVEL 2: Strong Differentiators (Next Phase)

After completing Level 1, these modules add depth and sophistication:

### 2.1 Memory Conflict Detection & Versioning

**Objective**  
Handle contradictory memories intelligently. When a user says "I'm allergic to peanuts" but previously said "I love peanut butter," the system should:
- Flag the contradiction
- Keep both memories but mark one as outdated
- Ask the user to clarify

**Impact:** +3–4 points (AI Creativity, Safety)

**Files to Create**
- `backend/app/memory/conflict_detection.py`

**Quick Outline**
- On memory insertion, search for contradictions (opposite assertions about the same entity)
- If found, mark old memory as `superseded=True` and link `version_id`
- Log conflicts for auditing

---

### 2.2 Reflective Memory Layer

**Objective**  
Let the AI analyze its own memory about the user. Every N conversations, Qwen reflects on what it knows:
- "Based on my memories, this user values efficiency and hates waiting"
- Use this reflection to improve future responses

**Impact:** +3–4 points (Innovation)

**Files to Create**
- `backend/app/memory/reflection.py`

---

### 2.3 User Feedback Loop

**Objective**  
Add thumbs up/down buttons to chat responses. Use feedback to adjust memory importance:
- Positive feedback → increase importance of related memories
- Negative feedback → decrease importance or mark as "unhelpful context"

**Impact:** +3–4 points (UX, Learning)

**Files to Modify**
- `frontend/src/components/Chat.jsx` (add feedback buttons)
- `backend/app/api/memories.py` (add feedback endpoint)

---

## LEVEL 3: Final Polish (Advanced)

### 3.1 Enhanced Dashboard & Visualizations

Show memory statistics, consolidation progress, and user insights in a dedicated Memory tab.

### 3.2 Demo Video Script & Recording

3-minute walkthrough: setup → chat → memory retrieval → consolidation example.

### 3.3 Final README & Blog Post

Strong feature highlights, architecture overview, and deployment instructions.

---

## Final Submission Checklist

Before submitting, ensure:

- [ ] **Level 1 Complete**
  - [ ] MCP server deployed and callable from Qwen
  - [ ] Consolidation task runs weekly, summaries stored
  - [ ] Benchmark results show 15%+ improvement
  - [ ] Architecture diagram in docs/ARCHITECTURE.md

- [ ] **Repository & Deployment**
  - [ ] Public GitHub repo with Apache 2.0 license
  - [ ] `infrastructure/acs_deployment.tf` visible and documented
  - [ ] `.gitignore` includes `.env`

- [ ] **Documentation**
  - [ ] README highlights memory features
  - [ ] AGENTS.md or similar explains agent architecture
  - [ ] Architecture diagram is clear and professional

- [ ] **Demo & Proof**
  - [ ] Benchmark results documented
  - [ ] MCP skills demonstrated working
  - [ ] At least one video demo (optional but encouraged)

- [ ] **Code Quality**
  - [ ] No debug prints or TODOs
  - [ ] Error handling throughout
  - [ ] Logging in place for debugging

---

## How to Use This Document

### For Immediate Completion (Next 2–3 Days)

1. **Start with Module 1.1 (MCP Integration)**
   - Copy the prompt under "Implementation Steps → Step 2" into Cursor
   - Follow the file creation steps
   - Verify the MCP endpoint works
   - Move to next module

2. **Then Module 1.2 (Consolidation)**
   - Create the consolidation module
   - Set up Celery Beat task
   - Verify with a manual trigger

3. **Then Module 1.3 (Benchmark)**
   - Run the script to prove value
   - Save results

4. **Finally Module 1.4 (Architecture)**
   - Create the diagram
   - Push all changes

### For Longer Timeline

- Complete Level 1 first (2–3 days)
- Assess score with judges' feedback
- Implement Level 2 modules (3–5 days)
- Final polish and demo (1–2 days)

---

## Key Success Factors

1. **Clear, working code** — Don't leave TODOs; finish each module before moving on
2. **Proper error handling** — Your system should be robust and production-ready
3. **Documentation** — Judges should understand your architecture without asking
4. **Measurable proof** — Benchmarks and logs provide confidence
5. **Iterative improvement** — Start with Level 1; expand based on feedback

---

## Questions & Troubleshooting

**"Where do I paste the prompt?"**  
Open Cursor (or your IDE) with the repo open. Create a new file (e.g., `backend/app/mcp/memory_skill.py`), then paste the prompt into the IDE's AI assistant chat (usually Cmd+K on Mac, Ctrl+K on Windows/Linux).

**"My Qwen API call fails."**  
Check that `DASHSCOPE_API_KEY` is set and `DASHSCOPE_BASE_URL` points to the international endpoint (already configured in `.env`).

**"The consolidation task doesn't run."**  
Ensure Redis is running and Celery Beat is active. Check logs for task scheduling errors.

**"Benchmark takes too long."**  
Reduce the number of scenarios from 12 to 6, or increase timeout for Qwen calls.

---

**Ready to start?**  
Begin with **Module 1.1** and follow the steps in order. Good luck! 🚀
