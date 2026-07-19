# Memoria – Self‑Evolving Personal AI with Human‑like Memory

**Elevator pitch:** A production‑grade MemoryAgent that remembers, forgets, resolves conflicts, and reflects on user knowledge – built on Qwen Cloud.

---

## Video Demonstrations

| Video | Link |
|-------|------|
| **Core Demo** – full feature walk‑through (2 min 58 s) | [https://youtu.be/ANFAl6bwjjI](https://youtu.be/ANFAl6bwjjI) |
| **Alibaba Cloud Live Deployment** – app running on ECS + infrastructure proof | [https://youtu.be/c1qJ6qr3IJk](https://youtu.be/c1qJ6qr3IJk) |

---

## Hackathon Details

- **Track:** Track 1 – MemoryAgent
- **Submitter:** Individual – Muhammad Awais
- **Country:** Pakistan
- **Project started:** July 09, 2026
- **Project type:** Newly built

---

## Submission Links

| Requirement | URL |
|-------------|-----|
| **Code repository** (public, Apache 2.0) | [https://github.com/imawais-engineer/Memoria](https://github.com/imawais-engineer/Memoria) |
| **Proof of Alibaba Cloud Deployment** (code file) | [infrastructure/acs_deployment.tf](https://github.com/imawais-engineer/Memoria/blob/main/infrastructure/acs_deployment.tf) |
| **Architecture Diagram** (live HTML) | [https://imawais-engineer.github.io/Memoria/Submission%20Files/architecture.html](https://imawais-engineer.github.io/Memoria/Submission%20Files/architecture.html) |
| **Architecture Diagram** (PNG) | [architecture.png](https://github.com/imawais-engineer/Memoria/blob/main/Submission%20Files/architecture.png) |
| **Blog Post** (dev.to) | [https://dev.to/imawais/memoria-a-self-evolving-personal-ai-with-human-like-memory-34p](https://dev.to/imawais/memoria-a-self-evolving-personal-ai-with-human-like-memory-34p) |
| **Live Demo** | [https://memoria.imawais.engineer](https://memoria.imawais.engineer) |

---

## AI Tools Leveraged

- Qwen AI (DashScope) – chat, memory extraction, embedding, media generation
- DeepSeek AI – assisted development / ideation
- Cursor AI IDE – code generation, debugging, refactoring
- Docker, Terraform, Alibaba Cloud – deployment and infrastructure

---

## Testing Instructions

1. Visit [https://memoria.imawais.engineer](https://memoria.imawais.engineer)
2. Click **Get Started** to open the sign‑up page.
3. Sign up with your **Name, Username, and Favorite Book**.
4. Login using your **Username and Favorite Book**.
5. Explore:
   - Chat (including `/imagine`, `/gen_video`, `/gen_voice`, `/memorize`, task commands)
   - Memory tab (stats, forget)
   - Personal Intelligence toggle (sidebar)
   - Memory‑less incognito sessions (button below New Chat)
   - Media, Tasks, Persona, Settings, Help, Feedback, About pages

No external credentials are required.

---

## Key Features (summary)

- Persistent multi‑session memory with three‑tier storage (Session, Personal, Context Archive)
- Autonomous memory lifecycle: extraction, embedding, decay, consolidation, conflict detection, reflection
- Personal Intelligence toggle (global vs. chat‑scoped memory)
- Memory‑Less incognito mode
- MCP skills server for external agents
- Nine chat slash commands with inline media generation
- Streaming chat with Markdown + LaTeX rendering
- User feedback loop (thumbs‑up/down) that adjusts memory importance
- Persona customisation
- Benchmark‑proven 77.6 % improvement in decision accuracy
- Alibaba Cloud deployment with Terraform infrastructure‑as‑code

---

**Author:** Muhammad Awais  
**Contact:** [@imawais_er](https://x.com/imawais_er)  
**License:** Apache 2.0
