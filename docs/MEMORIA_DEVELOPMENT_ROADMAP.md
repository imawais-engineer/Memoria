# Memoria – Development Roadmap

**Prompt-Driven, Module-by-Module Development**

This guide breaks the Memoria project into **10 sequential modules**.  
Each module tells you:

- What to build
- Which tools are used
- **The exact prompts** to give your AI IDE
- Key files and verification steps

You will work inside a single project folder (e.g., `memoria/`) and paste the prompts into your AI assistant (Cursor, Windsurf, etc.) to generate code.

---

## Table of Contents

1. [Module 1: Project Scaffold & Environment Setup](#module-1-project-scaffold--environment-setup)
2. [Module 2: Database Models & Memory Schema](#module-2-database-models--memory-schema)
3. [Module 3: Memory Ingestion Pipeline](#module-3-memory-ingestion-pipeline)
4. [Module 4: Memory Retrieval & Context Packing](#module-4-memory-retrieval--context-packing)
5. [Module 5: Forgetting & Consolidation Engine](#module-5-forgetting--consolidation-engine)
6. [Module 6: Core Chat Agent API](#module-6-core-chat-agent-api)
7. [Module 7: Session Management & Cross-Session Continuity](#module-7-session-management--cross-session-continuity)
8. [Module 8: Admin Dashboard (Frontend)](#module-8-admin-dashboard-frontend--optional-but-recommended)
9. [Module 9: Deployment to Alibaba Cloud & Proof of Use](#module-9-deployment-to-alibaba-cloud--proof-of-use)
10. [Module 10: Testing, Benchmarking & Documentation](#module-10-testing-benchmarking--documentation)
11. [Final Steps: Submission Package](#final-steps-submission-package)

---

## Module 1: Project Scaffold & Environment Setup

| | |
|---|---|
| **Objective** | Create the minimal project structure, virtual environment, dependencies, and Alibaba Cloud configuration. |
| **Tools used** | Python 3.11, FastAPI, DashScope SDK, SQLAlchemy, pgvector, Redis, Celery |
| **How it works** | We set up the folder structure and install everything needed for a modular backend. |

### AI IDE Prompt

Paste this into your assistant:

```text
Create a new Python project called "memoria" with the following structure:

memoria/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/
│   │   │   └── __init__.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   └── dashscope_client.py
│   │   ├── memory/
│   │   │   ├── __init__.py
│   │   │   ├── models.py
│   │   │   ├── ingestion.py
│   │   │   ├── retrieval.py
│   │   │   ├── forgetting.py
│   │   │   └── consolidation.py
│   │   ├── services/
│   │   │   └── agent_service.py
│   │   └── schemas/
│   │       └── memory.py
│   ├── celery_app/
│   │   ├── __init__.py
│   │   └── tasks.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── alembic.ini
├── frontend/               (we'll add later)
├── infrastructure/
│   └── acs_deployment.tf   (proof of Alibaba Cloud usage)
├── docs/
│   └── ARCHITECTURE.md
├── .env.example
├── .gitignore
├── README.md
└── LICENSE

Now write the requirements.txt with these exact packages:
fastapi
uvicorn[standard]
sqlalchemy
asyncpg
pgvector
psycopg2-binary
redis
celery[redis]
dashscope
python-dotenv
pydantic
pydantic-settings
alembic
openai  # if using OpenAI-compatible dashscope endpoint
httpx

Also create .env.example with placeholders:
DASHSCOPE_API_KEY=your_key
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/memoria
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=supersecret

Also generate a basic config.py that reads these env variables using pydantic-settings.

Set up a simple FastAPI app in main.py with a health check endpoint "/health".
```

### Verification

1. Run `uvicorn app.main:app --reload` inside the `backend` folder.
2. `curl localhost:8000/health` returns **200**.

---

## Module 2: Database Models & Memory Schema

| | |
|---|---|
| **Objective** | Define the `memories` table in PostgreSQL with pgvector extension, plus Alembic migrations. |
| **Tools used** | SQLAlchemy (async), pgvector, Alembic |
| **How it works** | The `Memory` model stores content, vector embedding, importance, decay rate, expiry, and metadata. We use a hybrid search index. |

### AI IDE Prompt

```text
In the file backend/app/memory/models.py, create an SQLAlchemy async model named Memory with the following columns:
- id: UUID primary key
- user_id: String, indexed
- type: String (one of 'core', 'episodic', 'semantic', 'procedural')
- content: Text
- embedding: Vector(1536)   # pgvector column
- importance: Float default 0.5
- created_at: DateTime with timezone, default utcnow
- last_accessed: DateTime with timezone
- expires_at: DateTime with timezone nullable
- decay_rate: Float default 0.01
- parent_id: UUID nullable (foreign key to self)
- metadata: JSONB default {}

Add a table-level index for (user_id, type) and a vector index using IVFFlat on embedding.

Write an Alembic migration that:
1. Creates the pgvector extension if not exists.
2. Creates the memories table with all constraints.

Also provide a script to init alembic (alembic init alembic) and configure alembic.ini to use our async DATABASE_URL.
```

### Verification

1. Run `alembic upgrade head` against a local PostgreSQL with pgvector.
2. Check the table with `\d memories`.

---

## Module 3: Memory Ingestion Pipeline

| | |
|---|---|
| **Objective** | Every message triggers a background process that uses **Qwen function calling** to extract structured memories, embeds them, and stores them. |
| **Tools used** | DashScope SDK (Qwen3‑Plus), text-embedding-v3, Celery |
| **How it works** | The agent passes the conversation turn to Qwen with a function definition for memory extraction. The model returns a list of memory items. Each is embedded and upserted. |

### AI IDE Prompt

```text
Create backend/app/memory/ingestion.py with an async function extract_and_store_memories(conversation_text: str, user_id: str, message_id: str, db_session).

Inside this function:
1. Use the DashScope client from core/dashscope_client.py (assume a function get_dashscope_client() that returns a client with api_key from config).
2. Call the Qwen3-Plus model with a function definition named "extract_memories". The function parameters should be a JSON schema:
   - memories: array of objects, each with fields:
     - content (string, required)
     - type (enum: core/episodic/semantic/procedural)
     - importance (number 0-1)
     - expires_in_hours (number, 0 means never)
3. Parse the function call response, and for each extracted memory:
   - Generate an embedding using DashScope's text-embedding-v3 (model name: text-embedding-v3, input the content).
   - Create a Memory record (from models.py) with user_id, type, content, embedding, importance, created_at=now, expires_at=now+hours if >0, decay_rate based on type (0.0 for core, 0.01 for semantic, 0.02 for episodic, 0.005 for procedural), and metadata including source_message_id.
   - Add to the database session and commit.

Wrap the function with error handling and logging. Make it a Celery task by adding @celery_app.task in celery_app/tasks.py that calls this function.

Also in core/dashscope_client.py, implement get_dashscope_client() using the dashscope SDK and the environment API key.
```

### Verification

1. Manually call `extract_and_store_memories.delay("I'm allergic to peanuts and I love sushi.", "user123", "msg1")`.
2. Check the database for new memory rows with embeddings.

---

## Module 4: Memory Retrieval & Context Packing

| | |
|---|---|
| **Objective** | Given a user query, retrieve the most relevant memories while respecting a token budget (e.g., 6000 tokens). Pack them into a context string for the LLM. |
| **Tools used** | pgvector hybrid search (cosine similarity + keyword boost), token counting (tiktoken or DashScope tokenizer) |
| **How it works** | We perform a vector similarity search, then re-rank and greedily pack until token limit. |

### AI IDE Prompt

```text
Create backend/app/memory/retrieval.py with an async function retrieve_context(user_id: str, query_text: str, max_tokens: int = 6000, db_session) -> str.

Steps:
1. Generate query embedding using text-embedding-v3.
2. Perform a raw SQL query (or use SQLAlchemy) to select top 50 memories for user_id, ordered by cosine similarity (embedding <=> query_embedding) multiplied by a freshness factor (decay applied importance). Exclude expired memories (expires_at < now if not null).
3. For each candidate, compute a relevance score = 0.7*similarity + 0.3*importance (normalized).
4. Sort by relevance descending.
5. Using a tokenizer (e.g., cl100k_base or DashScope token counting API), pack memories: start with an empty string and add memory content (prefixed with type and date) until adding the next would exceed max_tokens. Always include memories with type='core' first regardless of score.
6. Return the packed string.

Also add a helper function to count tokens using DashScope's token counting endpoint (if available) or fallback to tiktoken.

Make sure all DB access is async using asyncpg driver.
```

### Verification

1. Insert test memories, then call `retrieve_context` with a query.
2. Confirm that core memories are present and total length roughly stays under the limit.

---

## Module 5: Forgetting & Consolidation Engine

| | |
|---|---|
| **Objective** | Implement decay (daily) and consolidation (weekly) as scheduled Celery Beat tasks. |
| **Tools used** | Celery Beat, Redis scheduler, PostgreSQL |
| **How it works** | A daily task reduces importance based on exponential decay; a weekly task clusters similar memories and replaces them with summaries. |

### AI IDE Prompt

```text
In celery_app/tasks.py add two periodic tasks:

1. decay_memories (runs daily at 3am):
   - For all non-core memories of all users, update importance = importance * EXP(-decay_rate * EXTRACT(EPOCH FROM (NOW() - created_at))/86400).
   - For any memory with importance < 0.1, either delete it or archive it (add a field archived=True and move content to a JSON log).
   - Use raw SQL for performance.

2. consolidate_memories (runs weekly on Sunday at 4am):
   - For each user, group episodic and semantic memories created in the past 7 days.
   - Use pgvector to cluster them (e.g., DBSCAN on embeddings). For each cluster with >3 memories, call Qwen-Max to generate a single summary memory (type='semantic', importance=average of cluster, parent_id set to the oldest memory id).
   - Insert the summary and soft-delete the original memories (set archived=True or delete).
   - This mimics abstraction.

Provide configuration for Celery Beat schedule in celery_app/celeryconfig.py.

In forgetting.py (backend/app/memory/forgetting.py), implement the decay logic; in consolidation.py implement clustering and summarization using DashScope.
```

### Verification

1. Manually trigger `decay_memories.delay()` and check that importance values dropped.
2. Simulate a week of memories and run consolidation to see summaries.

---

## Module 6: Core Chat Agent API

| | |
|---|---|
| **Objective** | Expose a `/chat` endpoint that accepts a message, retrieves memory context, calls Qwen to generate a response, and then ingests new memories. |
| **Tools used** | FastAPI, DashScope, the memory modules |
| **How it works** | The endpoint orchestrates: retrieve context → build prompt → call Qwen → store conversation turn → trigger memory extraction. |

### AI IDE Prompt

```text
In backend/app/services/agent_service.py, create an async function handle_message(user_id: str, user_message: str, session_id: str) -> dict.

Steps:
1. Retrieve the user's short-term session buffer from Redis (list of recent messages).
2. Call memory.retrieval.retrieve_context(user_id, user_message, max_tokens=6000) to get a packed memory string.
3. Compose a system prompt: "You are a personal AI with memory. Here is what you know about the user: {memory_context}. Use this to personalize responses."
4. Build the message list: system prompt + session history + user_message.
5. Call Qwen3-Plus (or Max) via DashScope client to get a completion.
6. Store the conversation pair (user+assistant) in Redis with TTL.
7. Asynchronously trigger memory ingestion (celery task) passing the last conversation turn.
8. Return {"reply": assistant_text, "memories_used": token_breakdown?}.

Implement the FastAPI endpoint POST /chat in api/chat.py (create new file). The endpoint expects a JSON body with user_id, message, session_id (optional, auto-generate if missing). Use dependency injection for db and redis.

Add authentication stub (JWT) to secure endpoints, but for hackathon demo, a simple fixed token is okay.
```

### Verification

1. Start the server and send a `POST` to `/chat` with a message.
2. Check that the response references stored memories and that new memories appear in the DB.

---

## Module 7: Session Management & Cross-Session Continuity

| | |
|---|---|
| **Objective** | When a user returns after logging out, the agent recovers the last session state and relevant memories. |
| **Tools used** | Redis for session state, JWT or session tokens |
| **How it works** | The client sends a `session_token` that maps to a Redis hash storing `last_context_summary` and a rolling window of recent interactions. |

### AI IDE Prompt

```text
Enhance the /chat endpoint to handle session persistence.

- On first message (no session_id), create a new UUID session_id and store in Redis with a key `session:{session_id}` containing a JSON object with "messages": [] (last 10 messages) and "summary": "".
- On subsequent calls, retrieve the session object, update the message list, and also every 10 turns generate a short session summary using Qwen and store it to provide continuity if the context window is limited.
- When the user connects after a long gap, the agent can include the session summary in the system prompt to resume context.
- Include a way to fetch memory stats: GET /memories?user_id=... that returns count and a sample.

Write the logic in a new module backend/app/services/session_manager.py and integrate into chat endpoint.
```

### Verification

1. Simulate two separate sessions with the same `user_id`.
2. The second session should recall information from the first (via persistent memory, not just session cache).

---

## Module 8: Admin Dashboard (Frontend) – Optional but Recommended

| | |
|---|---|
| **Objective** | A minimal React app to visualise memory decay curves and manually trigger forgetting. |
| **Tools used** | React, D3.js, Axios |
| **How it works** | The frontend calls `/api/memories` to get a list and displays a graph. |

### AI IDE Prompt

```text
Create a React app in the frontend/ directory using create-react-app or Vite.

Build two components:
1. MemoryGraph: fetches memory data from the backend (GET /memories?user_id=...), then plots importance vs time for each memory using D3.js, with lines showing decay curves.
2. MemoryManager: a table of memories with a "Forget" button that calls DELETE /memories/{id}.

Add a simple login form that sends the demo token.

Ensure the backend has the corresponding API endpoints:
- GET /api/memories?user_id=... returns a list of memories (without embeddings).
- DELETE /api/memories/{id} removes a memory.
- GET /api/memory-stats returns aggregate data.

Add these endpoints in api/memories.py.
```

### Verification

1. Run the frontend and log in.
2. See memories and watch importance decline over time.

---

## Module 9: Deployment to Alibaba Cloud & Proof of Use

| | |
|---|---|
| **Objective** | Prepare infrastructure-as-code using Terraform to deploy ECS, PostgreSQL, Redis, and show proof of Alibaba Cloud usage. |
| **Tools used** | Terraform (alicloud provider), Docker |
| **How it works** | We define the cloud resources and a startup script that runs the FastAPI app and Celery workers. |

### AI IDE Prompt

```text
In infrastructure/acs_deployment.tf, write a Terraform configuration for Alibaba Cloud:
- Provider "alicloud" with region.
- An ECS instance (ecs_instance) with Ubuntu 22.04, security group opening ports 22 and 8000.
- ApsaraDB for PostgreSQL instance (rds) with pgvector support (choose a DB version that supports it).
- ApsaraDB for Redis instance.
- Output the connection strings.

Also provide a user_data script that:
1. Installs Docker and Docker Compose.
2. Pulls the project repo.
3. Builds the Docker image using the provided Dockerfile.
4. Runs the backend containers (app + celery worker + celery beat).
5. Sets environment variables from Terraform outputs.

Make sure to mention that this file proves Alibaba Cloud deployment.

Also create a Dockerfile in backend/ that builds the FastAPI app.
```

### Verification

1. Run `terraform plan` (or note that this file exists for judges).
2. The file must be in the repo.

---

## Module 10: Testing, Benchmarking & Documentation

| | |
|---|---|
| **Objective** | Show evidence that the memory system improves decision accuracy, and provide clear documentation. |
| **Tools used** | Pytest, manual simulation, Mermaid diagram |
| **How it works** | Write a test script that simulates a conversation with and without memory and measures accuracy. |

### AI IDE Prompt

```text
Create a test script in scripts/benchmark_memory.py that:
- Defines a synthetic user profile (allergies, preferences).
- Runs 10 turns with memory enabled and 10 turns without.
- Checks if the agent's response avoids allergens and respects preferences.
- Print accuracy percentages.

Write a few unit tests using pytest in tests/ for ingestion, retrieval, and context packing.

Update README.md with:
- Project description and features.
- Architecture diagram in Mermaid format (paste a sequence diagram showing user->chat endpoint->memory retrieval->Qwen->ingestion).
- Link to the architecture image.
- Instructions to run locally and deploy.
- Screenshots (placeholders).

Update docs/ARCHITECTURE.md with the full technical description.

Make sure LICENSE is Apache 2.0.
```

### Verification

1. Run tests with `pytest`.
2. The benchmark script should output improved accuracy.

---

## Final Steps: Submission Package

- [ ] Upload the complete repo to GitHub (public).
- [ ] Record a 3-minute demo following the earlier script.
- [ ] Write a blog post on dev.to / Medium about building Memoria.
- [ ] Submit the Devpost entry with all required links.

---

## Module Dependency Overview

```mermaid
flowchart LR
  M1[1. Scaffold] --> M2[2. Models]
  M2 --> M3[3. Ingestion]
  M2 --> M4[4. Retrieval]
  M3 --> M5[5. Forgetting]
  M4 --> M5
  M3 --> M6[6. Chat API]
  M4 --> M6
  M6 --> M7[7. Sessions]
  M6 --> M8[8. Dashboard]
  M1 --> M9[9. Alibaba Cloud]
  M6 --> M10[10. Tests & Docs]
  M7 --> M10
  M8 --> M10
  M9 --> M10
```

---

*Memoria — Qwen Cloud Hackathon project concept & development roadmap.*
