"""Live smoke test against a real OpenAI-compatible API.

Skipped unless LLM_API_KEY and LLM_BASE_URL are set in the environment. Models
come from LLM_CHAT_MODEL / LLM_EMBEDDING_MODEL (no key is ever written to disk).
"""

from __future__ import annotations

import os

import pytest

from app.config import Settings
from app.core.llm.openai_compat import OpenAICompatProvider

pytestmark = pytest.mark.skipif(
    not (os.getenv("LLM_API_KEY") and os.getenv("LLM_BASE_URL")),
    reason="LLM_API_KEY and LLM_BASE_URL not set",
)


def _provider() -> tuple[OpenAICompatProvider, Settings]:
    settings = Settings(_env_file=None)
    return OpenAICompatProvider(settings), settings


async def test_live_chat_and_stream():
    provider, settings = _provider()
    model = settings.llm_chat_model or "gpt-4o-mini"
    msgs = [{"role": "user", "content": "Reply with the single word: pong"}]
    assert (await provider.chat(msgs, model)).strip()
    events = [e async for e in provider.stream_events(msgs, model)]
    assert any(e.kind == "content" for e in events)


async def test_live_embedding():
    provider, settings = _provider()
    model = settings.llm_embedding_model or "text-embedding-v3"
    vector = await provider.embed("hello world", model)
    assert len(vector) == settings.embedding_dim
