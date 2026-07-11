**Project:** Memoria – Self-Evolving Personal AI with Human-like Memory  
**Track:** 1 – MemoryAgent  
**Version:** Upgrade Plan v1.0  
**Goal:** Elevate current implementation from ~64/100 to **Winning Level (88–94/100)**

---

## Executive Summary

This document provides a **modular, prompt-driven upgrade plan** to transform your existing Memoria codebase into a standout submission.

Each module includes:
- Objective & Scoring Impact
- Files to Modify/Create
- Exact Cursor / AI IDE Prompt
- Verification Steps

**Timeline Recommendation:** Complete Level 1 in 2–3 days.

---

## LEVEL 1: Must-Do Upgrades (Target: +12–15 points)

### Module 1: MCP Integration + Custom Skills

**Objective:** Expose Memory as a reusable skill via MCP and add custom tools. This directly addresses "sophisticated use of QwenCloud APIs" and "MCP integrations".

**Scoring Impact:** +5–6 points in Technical Depth & Engineering.

**Files to Create/Modify:**
- `backend/app/mcp/memory_skill.py`
- `backend/app/main.py` (register MCP)
- Update `requirements.txt` if needed

**AI IDE Prompt:**
We already have a working Memory system with PostgreSQL + pgvector.
Create a complete MCP skill server for memory access in backend/app/mcp/memory_skill.py.
Include these tools:

get_core_memories(user_id: str) -> list
get_user_preferences(user_id: str) -> dict
forget_memory(user_id: str, memory_id: str, reason: str) -> bool
strengthen_memory(user_id: str, memory_id: str) -> bool

Use the existing Memory model. Make it compatible with Qwen MCP standard.
Also register these skills in the main FastAPI app.
Add proper error handling and permission checks.


**Verification:** Test MCP endpoint and call skills from Qwen.

---

### Module 2: Advanced Memory Consolidation Engine

**Objective:** Implement weekly clustering + summarization to mimic human memory abstraction.

**Scoring Impact:** +4–5 points in Innovation & AI Creativity.

**Files to Create/Modify:**
- `backend/app/memory/consolidation.py`
- `celery_app/tasks.py` (add periodic task)
- `backend/app/memory/models.py` (add `parent_id` if missing)

**AI IDE Prompt:**
Implement a proper consolidation system.
In backend/app/memory/consolidation.py create an async function consolidate_memories(user_id: str).
Steps:

Fetch non-core memories from last 7 days for the user.
Use pgvector to find clusters (similarity threshold).
For each cluster (>3 memories), call Qwen-Max to generate a high-quality semantic summary memory.
Set parent_id on original memories and mark them as consolidated.
Insert the new summary memory with higher importance.

Add a Celery Beat task in celery_app/tasks.py that runs every Sunday at 4 AM.


**Verification:** Manually trigger task and check DB for summary memories.

---

### Module 3: Benchmark Suite & Quantitative Proof

**Objective:** Prove memory system improves decision quality over time.

**Scoring Impact:** +3–4 points in Problem Value & Impact.

**Files to Create:**
- `scripts/benchmark.py`

**AI IDE Prompt:**
Create scripts/benchmark.py that does the following:

Define a synthetic user profile (allergies, goals, preferences).
Run 12 simulated conversation turns WITHOUT memory system.
Run the same 12 turns WITH full memory system.
Measure:
Preference adherence accuracy
Safety compliance (e.g. allergy avoidance)
Coherence score

Output a clear table + percentage improvement.
Save results as JSON and generate a simple matplotlib chart.



**Verification:** Run `python scripts/benchmark.py` and review output.

---

### Module 4: Professional Architecture Diagram

**Objective:** Create a clear, judge-friendly visual.

**Files to Create/Modify:**
- `docs/ARCHITECTURE.md`

**AI IDE Prompt:**
Create a rich Mermaid architecture diagram for Memoria in docs/ARCHITECTURE.md.
Include:

Frontend (React)
FastAPI Backend
Redis Session Layer
PostgreSQL + pgvector Memory Store
Celery Workers (Ingestion, Decay, Consolidation)
DashScope / Qwen Cloud (Chat, Embedding, Function Calling, MCP)
MCP Skill Exposure
Flow arrows showing a chat request lifecycle.
Also add a short textual explanation below the diagram.


---

## LEVEL 2: Strong Differentiators (Next Phase)

### Module 5: Memory Conflict Detection & Versioning

**Objective:** Handle contradictory information intelligently.

### Module 6: Reflective Memory Layer

**Objective:** Agent analyzes its own knowledge about the user.

### Module 7: User Feedback Loop

**Objective:** Thumbs up/down improves future memory importance.

---

## LEVEL 3: Final Polish

### Module 8: Enhanced Dashboard + Visualizations

### Module 9: High-Quality Demo Video Script & Recording

### Module 10: Final README Polish + Blog Post Draft

---

## Final Submission Checklist (After All Modules)

- [ ] Public GitHub repo with Apache 2.0
- [ ] `infrastructure/acs_deployment.tf` clearly visible
- [ ] Rich Architecture diagram in `docs/ARCHITECTURE.md`
- [ ] 3-minute public YouTube demo video
- [ ] Benchmark results included
- [ ] MCP skills implemented and demonstrated
- [ ] Updated README with strong feature highlights
- [ ] Blog post (optional but recommended)

---

**How to Use This Document:**
1. Start with **Module 1 → Module 4** (Level 1).
2. Paste each **AI IDE Prompt** into Cursor.
3. Verify after each module.
4. Move to Level 2 once Level 1 is complete.

This structured upgrade plan is designed to maximize your score across all four judging criteria.

**Ready to begin?**  
Reply with **"Start Module 1"** and I will give you any supporting code or refinements needed.
