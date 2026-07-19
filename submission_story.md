# Memoria – A Self‑Evolving Personal AI with Human‑like Memory

Most AI assistants forget everything after each session. Memoria remembers, forgets, and evolves—extracting personal facts, resolving contradictions, and reflecting on what it knows. This post shares the journey of building a production‑ready MemoryAgent for the **Qwen Cloud Hackathon, Track 1**.

## Inspiration

Every conversation with a typical chatbot starts from zero. You tell it you're allergic to peanuts on Monday, and by Wednesday it recommends pad thai with crushed peanuts. The model doesn't forget; it never had long‑term memory in the first place. Without durable knowledge about who you are, real personalisation is impossible.

We built **Memoria** to solve that problem: a personal AI with human‑like memory that remembers what matters, forgets what fades, resolves contradictions, and evolves its understanding of you over time. Real memory isn't a bigger context window—it's extraction, prioritisation, decay, consolidation, and reflection. The hackathon challenged us to deliver a memory‑efficient, production‑grade MemoryAgent, and we built one from the ground up on Alibaba Cloud.

## What Memoria does

Memoria organises knowledge in three deliberate tiers:

- **Session Memory** (Redis) – the last 10 messages of the active chat.
- **Personal Memory** (PostgreSQL 16 + pgvector) – user‑centric facts embedded with `text-embedding-v3`, ranked by hybrid scoring, and subject to decay, consolidation, and conflict resolution.
- **Context Archive** – full transcripts stored for on‑demand search, never polluting routine retrieval.

Other key features:

- **Autonomous memory lifecycle**: daily decay, weekly consolidation, and background reflection.
- **Personal Intelligence toggle**: global memory access vs. session‑only.
- **Memory‑Less incognito mode**: no memory reads or writes.
- **MCP skills server**: exposes `get_core_memories`, `get_user_preferences`, `forget_memory`, and `strengthen_memory` to any Qwen agent.
- **Conflict detection & versioning**: contradictory facts are automatically flagged and superseded.
- **Persona customisation**: users set response length, tone, and behaviour.
- **Benchmark‑proven 77.6 % improvement** in decision accuracy across 12 realistic scenarios.
- **Live deployment on Alibaba Cloud ECS** with ApsaraDB for PostgreSQL and Redis, provisioned via Terraform.

## How we built it

**Backend**: Python FastAPI, SQLAlchemy async, PostgreSQL 16 + pgvector for hybrid vector search.  
**Memory pipeline**: DashScope – Qwen‑Plus for chat/extraction/conflict/reflection, Qwen‑Max for consolidation, `text-embedding-v3` for embeddings.  
**Background workers**: Celery handles memory ingestion, decay, and consolidation with Redis as the broker.  
**Frontend**: React + Vite, `react-markdown`, `remark‑math`, `rehype‑katex`, custom dark theme.  
**Deployment**: Docker Compose, Terraform for Alibaba Cloud (ECS, ApsaraDB, Redis), Let's Encrypt via Nginx.

## Challenges we ran into

- **Embedding dimension mismatch** (1536 → 1024) – fixed with an Alembic migration.
- **DashScope international endpoint** – defaulted to Beijing, required explicit config.
- **Model availability** – `qwen3-plus` not accessible; standardised on `qwen-plus`.
- **Markdown + LaTeX rendering** – needed multiple plugins and preprocessing.
- **Performance with conflict detection and reflection** – kept latency low by running them asynchronously in Celery.

## What we learned

- **Human‑like memory is harder than simple RAG** – it needs importance, decay, consolidation, and conflict resolution.
- **Qwen's tool‑calling and structured JSON output** make LLM pipelines reliable.
- **UX (PI toggle, Memory‑Less) matters as much as algorithms** – users must trust the memory.
- **Real‑infrastructure testing catches subtle bugs** – always deploy early.

## What's next

Voice input, multi‑agent collaboration via MCP, a mobile companion, advanced memory visualisations, and fine‑tuning Qwen on memory tasks.

---

**Try it yourself:** [https://memoria.imawais.engineer](https://memoria.imawais.engineer)  
**GitHub:** [imawais-engineer/Memoria](https://github.com/imawais-engineer/Memoria)

**Dev Post URL:** [https://dev.to/imawais/memoria-a-self-evolving-personal-ai-with-human-like-memory-34p](https://dev.to/imawais/memoria-a-self-evolving-personal-ai-with-human-like-memory-34p)

Built with ❤️ on **Alibaba Cloud** and **Qwen Cloud**.
