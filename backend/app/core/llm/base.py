"""Provider interface and shared helpers for LLM backends."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


class LLMError(RuntimeError):
    """Base error for provider failures."""


class UnsupportedCapabilityError(LLMError):
    """Raised when the active provider cannot do something (image, video, TTS)."""


class EmbeddingDimensionError(LLMError):
    """Raised when an embedding vector does not match EMBEDDING_DIM."""


@dataclass
class StreamEvent:
    """One streamed fragment: ``kind`` is ``content`` or ``reasoning``."""

    kind: str
    text: str


@runtime_checkable
class LLMProvider(Protocol):
    """Capabilities every provider exposes. Media methods may raise
    :class:`UnsupportedCapabilityError`."""

    name: str

    async def chat(self, messages: list[dict[str, Any]], model: str) -> str: ...

    def stream_events(
        self, messages: list[dict[str, Any]], model: str
    ) -> AsyncIterator[StreamEvent]: ...

    async def chat_with_tools(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], model: str
    ) -> Any: ...

    async def structured(
        self, messages: list[dict[str, Any]], json_schema: dict[str, Any], model: str
    ) -> dict[str, Any]: ...

    async def embed(self, text: str, model: str) -> list[float]: ...

    async def generate_image(self, prompt: str, model: str, size: str) -> str: ...

    async def generate_video(self, prompt: str, model: str, duration: int) -> str: ...

    async def synthesize_speech(self, text: str, model: str, voice: str) -> str: ...


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def strip_reasoning(text: str | None) -> str:
    """Remove inline ``<think>`` blocks so reasoning never leaks into content."""

    if not text:
        return ""
    cleaned = _THINK_RE.sub("", text)
    # Unterminated think block (truncated output): drop everything after it.
    idx = cleaned.lower().find("<think>")
    if idx != -1:
        cleaned = cleaned[:idx]
    return cleaned.strip() if cleaned != text else cleaned


def parse_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object from model text, tolerating fences and prose."""

    text = strip_reasoning(text).strip()
    candidates = [text]
    fenced = _FENCE_RE.search(text)
    if fenced:
        candidates.append(fenced.group(1).strip())
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])
    for cand in candidates:
        try:
            value = json.loads(cand)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(value, dict):
            return value
    raise LLMError("Model did not return a parseable JSON object")


def check_embedding_dim(vector: list[float], expected: int) -> list[float]:
    """Validate the length of an embedding vector."""

    if len(vector) != expected:
        raise EmbeddingDimensionError(
            f"Embedding has {len(vector)} dimensions but EMBEDDING_DIM={expected}. "
            "Pick an embedding model that returns the configured size, or migrate "
            "the pgvector column and re-embed (see docs/EMBEDDINGS.md)."
        )
    return vector
