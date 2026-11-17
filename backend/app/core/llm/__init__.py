"""Provider-agnostic LLM layer (OpenAI-compatible APIs and DashScope)."""

from __future__ import annotations

from app.config import get_settings, resolve_llm_provider
from app.core.llm.base import (
    EmbeddingDimensionError,
    LLMError,
    LLMProvider,
    StreamEvent,
    UnsupportedCapabilityError,
)

_cache: dict[tuple, LLMProvider] = {}


def get_provider() -> LLMProvider:
    """Return the provider selected by settings (cached per configuration)."""

    settings = get_settings()
    kind = resolve_llm_provider(settings)
    key = (kind, settings.llm_base_url, settings.llm_api_key)
    if key not in _cache:
        if kind == "openai":
            from app.core.llm.openai_compat import OpenAICompatProvider

            _cache[key] = OpenAICompatProvider(settings)
        else:
            from app.core.llm.dashscope_provider import DashScopeProvider

            _cache[key] = DashScopeProvider()
    return _cache[key]


def reset_provider_cache() -> None:
    _cache.clear()


__all__ = [
    "EmbeddingDimensionError",
    "LLMError",
    "LLMProvider",
    "StreamEvent",
    "UnsupportedCapabilityError",
    "get_provider",
    "reset_provider_cache",
]
