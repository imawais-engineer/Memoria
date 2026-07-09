# Memoria — 3-Minute Demo Video Script

**Goal:** show that Memoria remembers across sessions, retrieves the right
facts, and gracefully forgets — powered by Qwen Cloud + Alibaba Cloud.

**Setup before recording:**
- Backend running (`uvicorn app.main:app` + Celery worker) and frontend
  (`npm run dev`) at `http://localhost:5173`.
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
   show the assistant's friendly acknowledgement.

**Voiceover (over the send):**
> "I'll tell it one important fact — that I'm allergic to peanuts."

---

## Scene 2 — Cross-session continuity (0:45–1:30)

**Visual:** Open a **new** browser window / incognito (a brand-new session, no
shared history), same `user_id`.

**On screen:**
1. (0:45–1:00) Emphasize: "New window, new session — no chat history carried
   over."
2. (1:00–1:20) Type: **"What should I avoid eating?"** Show the reply correctly
   recalling **peanuts**.
3. (1:20–1:30) Switch to the **Memory** tab; point to the stored `core` memory
   **"Allergic to peanuts"** with its importance and type.

**Voiceover:**
> "In a completely separate session, I ask what to avoid — and Memoria remembers
> the peanut allergy. That recall comes from long-term memory stored in
> PostgreSQL with pgvector, retrieved by semantic similarity."

---

## Scene 3 — Forgetting (1:30–2:15)

**Visual:** Stay on the Memory tab.

**On screen:**
1. (1:30–1:45) Click **Forget** on a memory row; show it disappear from the list
   (and mention it's removed from the database).
2. (1:45–2:15) Cut to `docs/ARCHITECTURE.md` (the maintenance diagram) or the
   code in `backend/app/memory/forgetting.py` / `consolidation.py`.

**Voiceover:**
> "You're always in control — one click forgets a memory. Beyond manual
> deletion, Memoria forgets *automatically*: a daily job decays the importance
> of stale memories and archives the weak ones, while a weekly job clusters
> related memories and asks **Qwen-Max** to consolidate them into concise
> summaries — just like human memory."

---

## Scene 4 — Wrap-up & call to action (2:15–3:00)

**Visual:** Architecture diagram, then the GitHub repo.

**Voiceover:**
> "Under the hood: a **FastAPI** backend, **Qwen** on **DashScope** for chat,
> extraction, and embeddings, **PostgreSQL + pgvector** for memory, **Redis**
> for sessions, and **Celery** for background decay and consolidation — all
> deployable to **Alibaba Cloud** via Terraform."

**On screen:**
1. (2:15–2:35) Show the tech-stack / architecture slide.
2. (2:35–2:50) Show the GitHub repo (`imawais-engineer/Memoria`).
3. (2:50–3:00) Call to action.

**Voiceover (close):**
> "Memoria — a self-evolving personal AI that truly remembers. Star the repo,
> read the blog post, and give it a try. Built for the Qwen Cloud Hackathon,
> Track 1 – MemoryAgent."

---

### Shot list / B-roll checklist
- [ ] Chat sending "allergic to peanuts" (Scene 1)
- [ ] New session recalling peanuts (Scene 2)
- [ ] Memory tab with the stored fact (Scene 2)
- [ ] Forget button removing a memory (Scene 3)
- [ ] Architecture diagram from `docs/ARCHITECTURE.md` (Scenes 3–4)
- [ ] GitHub repo page (Scene 4)
