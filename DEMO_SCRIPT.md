# Memoria — 3-Minute Demo Video Script

**Goal:** show that Memoria remembers across sessions, retrieves the right
facts, learns from feedback, and gracefully forgets — powered by Qwen Cloud.

**Setup before recording:**
- Backend running (`uvicorn app.main:app` + Celery worker + Beat) and frontend
  (`npm run dev`) at `http://localhost:5173`, **or** use the live demo at
  [http://20.219.193.66](http://20.219.193.66).
- Two browser windows ready (a normal window and an incognito window) to
  demonstrate separate sessions.
- Pick a demo `user_id` (e.g. `demo-user`).

---

## Scene 1 — The problem & first memory (0:00–0:45)

**Visual:** Talking-head or slide, then cut to the Memoria chat UI.

**Voiceover:**
> "Most AI assistants have amnesia — every conversation starts from zero. Meet
> **Memoria**: a personal AI with human-like, long-term memory. Watch."

**On screen:**
1. (0:00–0:15) State the problem: "AI forgets everything between sessions."
2. (0:15–0:30) Open the chat, set the User ID to `demo-user`.
3. (0:30–0:45) Type: **"Hi! I'm Awais, and I'm allergic to peanuts."** Send, and
   show the assistant's friendly acknowledgement (rendered as **Markdown**).

**Voiceover (over the send):**
> "I'll tell it one important fact — that I'm allergic to peanuts. Behind the
> scenes, a Celery worker extracts that fact with Qwen function calling and
> stores it as an embedded memory."

---

## Scene 2 — Cross-session continuity (0:45–1:30)

**Visual:** Open a **new** browser window / incognito (a brand-new session, no
shared history), same `user_id`.

**On screen:**
1. (0:45–1:00) Emphasize: "New window, new session — no chat history carried
   over."
2. (1:00–1:20) Type: **"What should I avoid eating?"** Show the reply correctly
   recalling **peanuts** (Markdown-formatted response).
3. (1:20–1:30) Switch to the **Memory** tab; point to the stored `core` memory
   **"Allergic to peanuts"** with its importance and type.

**Voiceover:**
> "In a completely separate session, I ask what to avoid — and Memoria remembers
> the peanut allergy. That recall comes from long-term memory stored in
> PostgreSQL with pgvector, retrieved by semantic similarity."

---

## Scene 3 — Memory dashboard, stats & feedback (1:30–2:00)

**Visual:** Memory tab, then back to Chat.

**On screen:**
1. (1:30–1:40) On the **Memory** tab, show the **stats cards** (total memories,
   consolidated count, average importance) and the **horizontal bar chart**
   breaking down memories by type (`core`, `preference`, `episodic`, etc.).
2. (1:40–1:50) Return to **Chat**; on the assistant's allergy-aware reply,
   click the **👍 thumbs-up** button. Note it strengthens the memories that
   informed that answer (`POST /api/feedback`).
3. (1:50–2:00) Optionally click **👎** on a wrong reply to show weakening.

**Voiceover:**
> "The Memory dashboard shows live stats and a type breakdown. And when the
> agent gets it right, a thumbs-up strengthens the underlying memories — a
> human-in-the-loop feedback loop."

---

## Scene 4 — Forgetting & autonomous maintenance (2:00–2:30)

**Visual:** Stay on the Memory tab, then cut to architecture.

**On screen:**
1. (2:00–2:10) Click **Forget** on a memory row; show it disappear from the list
   (removed from the database).
2. (2:10–2:30) Cut to `docs/ARCHITECTURE.md` (the Mermaid diagram) — highlight
   decay, consolidation, conflict detection, and reflection nodes.

**Voiceover:**
> "You're always in control — one click forgets a memory. Beyond manual
> deletion, Memoria forgets *automatically*: a daily job decays stale memories,
> a weekly job clusters related facts and asks **Qwen-Max** to consolidate them,
> and conflict detection supersedes outdated facts when you change your mind."

---

## Scene 5 — MCP skills & wrap-up (2:30–3:00)

**Visual:** Swagger UI or `curl`, then architecture diagram, then GitHub repo.

**On screen:**
1. (2:30–2:40) Show `GET /mcp/memory-skills` in Swagger (`/docs`) or run:
   ```bash
   curl http://localhost:8000/mcp/memory-skills
   ```
   Highlight the four tools: `get_core_memories`, `get_user_preferences`,
   `forget_memory`, `strengthen_memory`.
2. (2:40–2:50) Show the architecture diagram from `docs/ARCHITECTURE.md`.
3. (2:50–3:00) Show the GitHub repo and live demo link.

**Voiceover:**
> "External agents can plug in via MCP memory skills — query preferences, forget
> stale facts, or strengthen important ones. Under the hood: **FastAPI**,
> **Qwen** on **DashScope**, **PostgreSQL + pgvector**, **Redis**, and
> **Celery** — deployed on Azure with Alibaba Cloud Terraform proof."

**Voiceover (close):**
> "Memoria — a self-evolving personal AI that truly remembers. Star the repo,
> watch the demo video, and give it a try. Built for the Qwen Cloud Hackathon,
> Track 1 – MemoryAgent."

---

### Shot list / B-roll checklist
- [ ] Chat sending "allergic to peanuts" with Markdown reply (Scene 1)
- [ ] New session recalling peanuts (Scene 2)
- [ ] Memory tab with stored fact (Scene 2)
- [ ] Stats cards + type bar chart on Memory tab (Scene 3)
- [ ] Thumbs-up feedback on assistant message (Scene 3)
- [ ] Forget button removing a memory (Scene 4)
- [ ] Architecture diagram from `docs/ARCHITECTURE.md` (Scenes 4–5)
- [ ] MCP endpoint in Swagger or curl output (Scene 5)
- [ ] GitHub repo page + live demo URL (Scene 5)
