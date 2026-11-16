"""Backwards compatible facade over the provider layer in ``app.core.llm``.

All AI calls in the app go through the names in this module (``call_qwen_chat``,
``stream_qwen_chat``, ``get_embedding`` ...). They dispatch to the provider
selected by ``LLM_PROVIDER`` (any OpenAI-compatible API, or DashScope). The
function names are kept so existing imports and test patches keep working.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.config import get_settings, resolve_llm_provider
from app.core.llm import get_provider
from app.core.llm.base import (
    EmbeddingDimensionError,
    LLMError,
    UnsupportedCapabilityError,
    check_embedding_dim,
)
from app.core.llm.dashscope_provider import (  # noqa: F401  (re-exported)
    IMAGE_DEFAULT_SIZE,
    IMAGE_MODEL,
    TTS_MODEL,
    TTS_VOICE,
    VIDEO_DEFAULT_DURATION,
    VIDEO_MODEL,
    get_dashscope_client,
)

_settings = get_settings()
IS_OPENAI_PROVIDER = resolve_llm_provider(_settings) == "openai"

# Default embedding model (mapped to LLM_EMBEDDING_MODEL on OpenAI providers).
DEFAULT_EMBEDDING_MODEL = "text-embedding-v3"


def _build_chat_models() -> list[dict[str, str]]:
    if not IS_OPENAI_PROVIDER:
        return [
            {"id": "qwen-plus", "name": "Qwen Plus (balanced)"},
            {"id": "qwen-max", "name": "Qwen Max (powerful)"},
            {"id": "qwq-plus", "name": "QwQ Plus (reasoning)"},
            {"id": "qwen-turbo", "name": "Qwen Turbo (fast)"},
        ]
    ids = [m.strip() for m in _settings.llm_chat_models.split(",") if m.strip()]
    primary = _settings.llm_chat_model.strip() or (ids[0] if ids else "") or (
        _settings.llm_fast_model.strip() or "gpt-4o-mini"
    )
    if primary not in ids:
        ids.insert(0, primary)
    return [{"id": i, "name": i} for i in ids]


# Chat models exposed to the frontend model switcher.
CHAT_MODELS = _build_chat_models()
ALLOWED_CHAT_MODELS = {item["id"] for item in CHAT_MODELS}
DEFAULT_CHAT_MODEL = (
    (_settings.llm_chat_model.strip() or CHAT_MODELS[0]["id"])
    if IS_OPENAI_PROVIDER
    else "qwen-plus"
)
# Model for memory extraction / tool calling / structured output.
DEFAULT_MODEL = (
    (_settings.llm_fast_model.strip() or DEFAULT_CHAT_MODEL)
    if IS_OPENAI_PROVIDER
    else "qwen3-plus"
)


async def call_qwen_with_functions(
    messages: list[dict[str, Any]],
    functions: list[dict[str, Any]],
    model: str = DEFAULT_MODEL,
) -> Any:
    """Chat with tool definitions. Returns an object with
    ``.output["choices"][0]["message"]`` (``tool_calls`` inside)."""

    return await get_provider().chat_with_tools(messages, functions, model)


async def call_qwen_structured(
    messages: list[dict[str, Any]],
    json_schema: dict[str, Any],
    model: str = "qwen-plus",
) -> dict[str, Any]:
    """Return a JSON object conforming to ``json_schema``."""

    return await get_provider().structured(messages, json_schema, model)


async def call_qwen_chat(
    messages: list[dict[str, Any]],
    model: str = DEFAULT_MODEL,
) -> str:
    """Plain text completion. Reasoning content is never included."""

    return await get_provider().chat(messages, model)


async def stream_qwen_chat(
    messages: list[dict[str, Any]],
    model: str = DEFAULT_MODEL,
) -> AsyncIterator[str]:
    """Stream answer tokens (reasoning is filtered out)."""

    async for event in get_provider().stream_events(messages, model):
        if event.kind == "content":
            yield event.text


async def stream_chat_events(
    messages: list[dict[str, Any]],
    model: str = DEFAULT_MODEL,
):
    """Stream ``StreamEvent`` items, with reasoning separated from content."""

    async for event in get_provider().stream_events(messages, model):
        yield event


async def get_embedding(
    text_input: str,
    model: str = DEFAULT_EMBEDDING_MODEL,
) -> list[float]:
    """Return the embedding for ``text_input``, validated against EMBEDDING_DIM."""

    vector = await get_provider().embed(text_input, model)
    return check_embedding_dim(vector, get_settings().embedding_dim)


async def generate_image(
    prompt: str,
    model: str = IMAGE_MODEL,
    size: str = IMAGE_DEFAULT_SIZE,
) -> str:
    """Generate an image and return its URL (DashScope only)."""

    return await get_provider().generate_image(prompt, model, size)


async def generate_video(
    prompt: str,
    model: str = VIDEO_MODEL,
    duration: int = VIDEO_DEFAULT_DURATION,
) -> str:
    """Generate a video and return its URL (DashScope only)."""

    return await get_provider().generate_video(prompt, model, duration)


async def synthesize_speech(
    text: str,
    model: str = TTS_MODEL,
    voice: str = TTS_VOICE,
) -> str:
    """Synthesize speech and return an audio URL (DashScope only)."""

    return await get_provider().synthesize_speech(text, model, voice)


__all__ = [
    "ALLOWED_CHAT_MODELS",
    "CHAT_MODELS",
    "DEFAULT_CHAT_MODEL",
    "DEFAULT_EMBEDDING_MODEL",
    "DEFAULT_MODEL",
    "EmbeddingDimensionError",
    "LLMError",
    "UnsupportedCapabilityError",
    "call_qwen_chat",
    "call_qwen_structured",
    "call_qwen_with_functions",
    "generate_image",
    "generate_video",
    "get_embedding",
    "stream_qwen_chat",
    "synthesize_speech",
]
