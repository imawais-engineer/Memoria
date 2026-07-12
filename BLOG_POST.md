# Building Memoria: A Self-Evolving MemoryAgent on Qwen Cloud

*Draft for Medium / dev.to — replace `[Your Name]` and publish URL when live.*

---

## The problem

Every chatbot starts from zero. You tell an assistant you're allergic to peanuts on Monday, and by Wednesday it recommends pad thai with crushed peanuts. The model didn't forget — it never had long-term memory in the first place.

**Memoria** fixes that. It's a production-grade MemoryAgent that remembers, forgets, resolves conflicts, and reflects on what it knows about you — all built on **Qwen Cloud (DashScope)**.

## What we built

Memoria is a full-stack memory system, not a prompt hack:

1. **Extract** — after each chat turn, a Celery worker calls Qwen with function calling to pull out facts (allergies, preferences, goals).
2. **Embed & store** — facts become 1024-dim vectors (`text-embedding-v3`) in PostgreSQL + pgvector.
3. **Retrieve** — the next reply ranks memories by similarity × importance × recency, always surfacing `core` facts first.
4. **Forget** — daily decay archives stale memories; weekly Qwen-Max consolidation clusters related facts into summaries.
5. **Evolve** — conflict detection supersedes outdated facts; reflection surfaces higher-level insights every 10 messages; thumbs-up/down feedback strengthens or weakens memories.

External agents can query and curate memory via **MCP skills** (`GET /mcp/memory-skills`).

## The numbers

We benchmarked 12 realistic scenarios (dietary restrictions, allergies, weekend plans). With memory injected, Qwen's replies scored **77.6% higher** on average — including +460% on meal-prep planning where the baseline had no user context at all.

## Try it

- **Live demo:** [http://20.219.193.66](http://20.219.193.66)
- **Repo:** [github.com/imawais-engineer/Memoria](https://github.com/imawais-engineer/Memoria)
- **Demo video:** [YouTube URL TBD]

Built for the **Qwen Cloud Hackathon, Track 1 – MemoryAgent**.

---

*By [Your Name]. Questions? Open an issue on GitHub.*
