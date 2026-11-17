"""Provider for any OpenAI-compatible API (chat/completions, embeddings)."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import httpx

from app.config import Settings
from app.core.llm.base import (
    LLMError,
    StreamEvent,
    UnsupportedCapabilityError,
    parse_json_object,
    strip_reasoning,
)

logger = logging.getLogger(__name__)

# Model ids hard-coded in older call sites; mapped to the configured models.
_LEGACY_FAST = {"qwen-turbo", "qwen3-plus"}
_LEGACY_CHAT = {"qwen-plus", "qwen-max", "qwq-plus"}
_LEGACY_EMBEDDING = {"text-embedding-v3"}
_RETRY_STATUS = {429, 500, 502, 503, 504}


class OpenAICompatProvider:
    """Talks to ``{LLM_BASE_URL}/chat/completions`` and ``/embeddings``."""

    name = "openai"

    def __init__(self, settings: Settings) -> None:
        if not settings.llm_base_url.strip():
            raise LLMError("LLM_BASE_URL is required for the openai provider")
        self._s = settings
        self._base = settings.llm_base_url.strip().rstrip("/")
        self._structured_mode = "json_schema"  # downgraded when unsupported

    # -- helpers ---------------------------------------------------------
    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._s.llm_api_key:
            headers["Authorization"] = f"Bearer {self._s.llm_api_key}"
        return headers

    def resolve_model(self, model: str) -> str:
        s = self._s
        fast = s.llm_fast_model or s.llm_chat_model
        if model in _LEGACY_FAST and fast:
            return fast
        if model in _LEGACY_CHAT and s.llm_chat_model:
            return s.llm_chat_model
        return model

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self._s.llm_timeout_seconds)

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base}{path}"
        async with self._client() as client:
            for attempt in range(3):
                try:
                    resp = await client.post(url, json=payload, headers=self._headers())
                except httpx.TransportError as exc:
                    if attempt == 2:
                        raise LLMError(f"LLM request to {path} failed: {exc}") from exc
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                if resp.status_code in _RETRY_STATUS and attempt < 2:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                if resp.status_code >= 400:
                    raise _http_error(path, resp.status_code, resp.text)
                return resp.json()
        raise LLMError("unreachable")  # pragma: no cover

    @staticmethod
    def _message(data: dict[str, Any]) -> dict[str, Any]:
        try:
            return data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("Malformed chat completion response") from exc

    # -- chat ------------------------------------------------------------
    async def chat(self, messages: list[dict[str, Any]], model: str) -> str:
        data = await self._post(
            "/chat/completions",
            {"model": self.resolve_model(model), "messages": messages},
        )
        return strip_reasoning(self._message(data).get("content"))

    async def stream_events(
        self, messages: list[dict[str, Any]], model: str
    ) -> AsyncIterator[StreamEvent]:
        payload = {
            "model": self.resolve_model(model),
            "messages": messages,
            "stream": True,
        }
        in_think = False
        buffer = ""
        async with self._client() as client:
            async with client.stream(
                "POST",
                f"{self._base}/chat/completions",
                json=payload,
                headers=self._headers(),
            ) as resp:
                if resp.status_code >= 400:
                    body = (await resp.aread()).decode("utf-8", "replace")
                    raise _http_error("/chat/completions", resp.status_code, body)
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line or line.startswith(":") or not line.startswith("data:"):
                        continue
                    chunk = line[5:].strip()
                    if chunk == "[DONE]":
                        break
                    try:
                        obj = json.loads(chunk)
                    except json.JSONDecodeError:
                        continue
                    if obj.get("error"):
                        raise LLMError(f"LLM stream error: {obj['error']}")
                    choices = obj.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    reasoning = delta.get("reasoning_content") or delta.get("reasoning")
                    if reasoning:
                        yield StreamEvent("reasoning", reasoning)
                    content = delta.get("content")
                    if not content:
                        continue
                    # Route inline <think>...</think> to the reasoning channel.
                    buffer += content
                    while buffer:
                        if in_think:
                            end = buffer.lower().find("</think>")
                            if end == -1:
                                keep = _partial_tag_len(buffer, "</think>")
                                emit = buffer[: len(buffer) - keep]
                                buffer = buffer[len(buffer) - keep :]
                                if emit:
                                    yield StreamEvent("reasoning", emit)
                                break
                            else:
                                if end:
                                    yield StreamEvent("reasoning", buffer[:end])
                                buffer = buffer[end + len("</think>") :]
                                in_think = False
                        else:
                            start = buffer.lower().find("<think>")
                            if start == -1:
                                keep = _partial_tag_len(buffer, "<think>")
                                emit = buffer[: len(buffer) - keep]
                                buffer = buffer[len(buffer) - keep :]
                                if emit:
                                    yield StreamEvent("content", emit)
                                break
                            if start:
                                yield StreamEvent("content", buffer[:start])
                            buffer = buffer[start + len("<think>") :]
                            in_think = True
        if buffer and not in_think:
            yield StreamEvent("content", buffer)

    async def chat_with_tools(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], model: str
    ) -> Any:
        data = await self._post(
            "/chat/completions",
            {"model": self.resolve_model(model), "messages": messages, "tools": tools},
        )
        message = dict(self._message(data))
        message["content"] = strip_reasoning(message.get("content"))
        message.pop("reasoning_content", None)
        # Same shape the DashScope SDK returns so existing parsers keep working.
        return SimpleNamespace(
            status_code=200,
            output={"choices": [{"message": message}]},
            raw=data,
        )

    async def structured(
        self, messages: list[dict[str, Any]], json_schema: dict[str, Any], model: str
    ) -> dict[str, Any]:
        """json_schema, then json_object, then prompt+parse. A mode rejected by
        the server (HTTP 4xx) is remembered so later calls skip it."""

        resolved = self.resolve_model(model)
        order = ["json_schema", "json_object", "prompt"]
        modes = order[order.index(self._structured_mode) :]
        last_error: LLMError | None = None
        for mode in modes:
            payload: dict[str, Any] = {"model": resolved, "messages": messages}
            if mode == "json_schema":
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "structured_output",
                        "schema": json_schema,
                        "strict": True,
                    },
                }
            else:
                payload["messages"] = _with_schema_prompt(messages, json_schema)
                if mode == "json_object":
                    payload["response_format"] = {"type": "json_object"}
            try:
                data = await self._post("/chat/completions", payload)
                return parse_json_object(self._message(data).get("content") or "")
            except _ClientRejected as exc:
                logger.info("structured mode %s rejected; falling back", mode)
                last_error = exc
                if mode != "prompt":
                    self._structured_mode = order[order.index(mode) + 1]
            except LLMError as exc:
                if "parseable" not in str(exc):
                    raise
                logger.info("structured mode %s output unparseable", mode)
                last_error = exc
        raise last_error or LLMError("Structured output failed")

    # -- embeddings ------------------------------------------------------
    async def embed(self, text: str, model: str) -> list[float]:
        name = model
        if model in _LEGACY_EMBEDDING and self._s.llm_embedding_model:
            name = self._s.llm_embedding_model
        payload: dict[str, Any] = {"model": name, "input": text}
        if self._s.llm_embedding_send_dimensions:
            payload["dimensions"] = self._s.embedding_dim
        data = await self._post("/embeddings", payload)
        try:
            return [float(x) for x in data["data"][0]["embedding"]]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("Malformed embeddings response") from exc

    # -- media (DashScope only) -----------------------------------------
    async def generate_image(self, prompt: str, model: str, size: str) -> str:
        raise _unsupported("Image generation")

    async def generate_video(self, prompt: str, model: str, duration: int) -> str:
        raise _unsupported("Video generation")

    async def synthesize_speech(self, text: str, model: str, voice: str) -> str:
        raise _unsupported("Speech synthesis")


class _ClientRejected(LLMError):
    """HTTP 4xx (not auth/rate limit) typically meaning an unsupported parameter."""


def _unsupported(what: str) -> UnsupportedCapabilityError:
    return UnsupportedCapabilityError(
        f"{what} is only available with LLM_PROVIDER=dashscope; "
        "the OpenAI-compatible provider does not support it."
    )


def _http_error(path: str, status: int, body: str) -> LLMError:
    snippet = body[:300].replace("\n", " ")
    msg = f"LLM request to {path} failed with HTTP {status}: {snippet}"
    if status in (400, 404, 415, 422):
        return _ClientRejected(msg)
    return LLMError(msg)


def _partial_tag_len(text: str, tag: str) -> int:
    """Length of a trailing fragment that could be the start of ``tag``."""

    lowered = text.lower()
    for n in range(min(len(tag) - 1, len(lowered)), 0, -1):
        if tag.startswith(lowered[-n:]):
            return n
    return 0


def _with_schema_prompt(
    messages: list[dict[str, Any]], schema: dict[str, Any]
) -> list[dict[str, Any]]:
    instruction = (
        "Respond with a single JSON object only, no prose, matching this JSON "
        f"schema: {json.dumps(schema)}"
    )
    return [*messages, {"role": "system", "content": instruction}]
