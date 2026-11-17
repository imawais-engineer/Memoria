# Memoria MCP server

Memoria exposes long-term memory to any MCP client with three tools:

| Tool | Arguments | Result |
| --- | --- | --- |
| `remember` | `text`, optional `session_id` | Extracts and stores durable memories from `text`. |
| `recall` | `query`, optional `include_superseded` | Matching memories, each with a `why` breakdown (similarity, recency, importance). |
| `forget` | `memory_id` | Deletes one of the caller's memories. |

Memory access is always scoped to the authenticated user. `remember` uses the
configured LLM and embedding provider (see `docs/LLM_PROVIDERS.md`).

## Authentication

* **HTTP**: send `Authorization: Bearer <JWT>`, the same access token the REST
  API issues from `/api/auth`. Missing or invalid tokens get `401`.
* **stdio**: set `MEMORIA_MCP_TOKEN` to a JWT, or `MEMORIA_MCP_USER_ID` to a
  user UUID (local single-user use only; it skips token checks). The process
  also needs the backend environment (`DATABASE_URL`, `SECRET_KEY`, LLM keys).

Never commit tokens. Pass them through your client's environment settings.

## Remote (streamable HTTP)

The FastAPI app mounts the server at `/mcp/`.

```json
{
  "mcpServers": {
    "memoria": {
      "url": "https://your-host/mcp/",
      "headers": { "Authorization": "Bearer ${MEMORIA_TOKEN}" }
    }
  }
}
```

Claude Code: `claude mcp add --transport http memoria https://your-host/mcp/ --header "Authorization: Bearer $MEMORIA_TOKEN"`

## Local (stdio)

```json
{
  "mcpServers": {
    "memoria": {
      "command": "python",
      "args": ["-m", "app.mcp.server"],
      "cwd": "/path/to/Memoria/backend",
      "env": { "MEMORIA_MCP_TOKEN": "<jwt>" }
    }
  }
}
```

## Design notes

The server uses the official `mcp` Python SDK (`mcp>=1.9,<2`) in stateless
JSON mode. The tool catalog in `app/mcp/memory_skill.py` is separate: it lists
function-calling tools for the chat agent and is not an MCP server.
