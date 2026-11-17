# LLM providers

Memoria talks to models through `app/core/llm/`. Select a provider with
environment variables (placeholders in `.env.example`; never commit keys).

| Provider | When | Needs |
|---|---|---|
| `openai` (any OpenAI-compatible API) | `LLM_BASE_URL` is set, or `LLM_PROVIDER=openai` | `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_CHAT_MODEL` |
| `dashscope` | default when `LLM_BASE_URL` is empty | `DASHSCOPE_API_KEY` |

## Capabilities on the OpenAI-compatible provider

- Chat and SSE streaming (`/chat/completions`, `stream: true`).
- Tool calling (`tools` / `tool_calls`), used for memory extraction.
- Structured output: tries `json_schema`, falls back to `json_object`, then to a
  prompt plus tolerant JSON parsing. The mode a server rejects is remembered.
- Embeddings (`/embeddings`), validated against `EMBEDDING_DIM`.
- Reasoning models: `reasoning_content` and inline `<think>` blocks are kept
  out of replies and out of stored memories. Streaming exposes them as separate
  `reasoning` events (`stream_chat_events`).
- Not supported: image, video and voice generation (`/imagine`, `/gen_video`,
  `/gen_voice`). The API returns HTTP 501 with an explanation and no quota is used.

Older call sites still pass names like `qwen-plus`; on the OpenAI provider these
map to `LLM_CHAT_MODEL` (and `qwen-turbo` / `qwen3-plus` to `LLM_FAST_MODEL`).

## Examples

```env
# Qwen OpenAI-compatible endpoint
LLM_BASE_URL=https://ap-southeast-1.maas.qwencloudapi.com/compatible-mode/v1
LLM_CHAT_MODEL=qwen3.8-flash
LLM_FAST_MODEL=qwen3.8-flash
LLM_CHAT_MODELS=qwen3.8-flash,qwen3.8-max,qwen3.7-plus,qwen4-max,deepseek-v4.1-flash
LLM_EMBEDDING_MODEL=text-embedding-v3
```

For OpenAI itself use `https://api.openai.com/v1`, a chat model, and
`text-embedding-3-small` with `LLM_EMBEDDING_SEND_DIMENSIONS=true`.

## Testing

`backend/tests/mock_openai_server.py` is a local OpenAI-compatible server used by
`tests/test_llm_providers.py`. `tests/test_live_openai_compat.py` runs only when
`LLM_API_KEY` and `LLM_BASE_URL` are set in the environment.
