"""DashScope (Qwen) client helpers.

Provides a configured DashScope handle and an awaitable wrapper around Qwen
function/tool calling for use by the memory ingestion pipeline.

The DashScope SDK's ``Generation.call`` is synchronous and network-bound, so we
run it in a worker thread via ``asyncio.to_thread`` to keep the async event loop
responsive.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import queue
import threading
from collections.abc import AsyncIterator
from http import HTTPStatus
from types import ModuleType
from typing import Any

import dashscope

from app.config import get_settings

logger = logging.getLogger(__name__)

# Default Qwen model used for memory extraction / tool calling.
DEFAULT_MODEL = "qwen3-plus"

# Chat models exposed to the frontend model switcher.
CHAT_MODELS = [
    {"id": "qwen-plus", "name": "Qwen Plus (balanced)"},
    {"id": "qwen-max", "name": "Qwen Max (powerful)"},
    {"id": "qwq-plus", "name": "QwQ Plus (reasoning)"},
    {"id": "qwen-turbo", "name": "Qwen Turbo (fast)"},
]
ALLOWED_CHAT_MODELS = {item["id"] for item in CHAT_MODELS}
DEFAULT_CHAT_MODEL = "qwen-plus"

# Multimodal generation models (DashScope / Qwen Cloud console IDs).
IMAGE_MODEL = "wan2.1-t2i-plus"
VIDEO_MODEL = "wan2.1-t2v-turbo"
TTS_MODEL = "qwen3-tts-flash"
TTS_VOICE = "Cherry"

# Official defaults per https://docs.qwencloud.com (no user-facing overrides).
IMAGE_DEFAULT_SIZE = "1280*1280"
VIDEO_DEFAULT_DURATION = 5

# Default embedding model.
DEFAULT_EMBEDDING_MODEL = "text-embedding-v3"


def get_dashscope_client() -> ModuleType:
    """Configure and return the DashScope module.

    The DashScope SDK is module-global: setting ``dashscope.api_key`` configures
    all subsequent calls. We source the key from application settings, falling
    back to the ``DASHSCOPE_API_KEY`` environment variable if settings are empty.
    Returns the ``dashscope`` module so callers can invoke its APIs directly.
    """

    settings = get_settings()
    api_key = (
        settings.dashscope_api_key
        or settings.qwen_dashscope_api
        or os.getenv("DASHSCOPE_API_KEY", "")
        or os.getenv("QWEN_DASHSCOPE_API", "")
    )

    if not api_key:
        # Not fatal at import/config time; the actual API call will fail clearly
        # if it proceeds without a key.
        logger.warning(
            "DASHSCOPE_API_KEY is not set; DashScope calls will fail until it is "
            "configured."
        )

    dashscope.api_key = api_key

    # Apply an endpoint override when configured (e.g. international region).
    if settings.dashscope_base_url:
        dashscope.base_http_api_url = settings.dashscope_base_url

    return dashscope


async def call_qwen_with_functions(
    messages: list[dict[str, Any]],
    functions: list[dict[str, Any]],
    model: str = DEFAULT_MODEL,
) -> Any:
    """Call Qwen with tool/function definitions and return the raw response.

    Args:
        messages: Chat messages in DashScope format
            (``[{"role": "user", "content": "..."}, ...]``).
        functions: Tool/function definitions passed as ``tools``.
        model: Qwen model name (defaults to :data:`DEFAULT_MODEL`).

    Returns:
        The DashScope ``GenerationResponse`` object.

    Raises:
        RuntimeError: If the API returns a non-OK status code or the SDK call
            raises. Errors are logged before being re-raised.
    """

    client = get_dashscope_client()

    def _invoke() -> Any:
        return client.Generation.call(
            model=model,
            messages=messages,
            tools=functions,
            result_format="message",
        )

    try:
        response = await asyncio.to_thread(_invoke)
    except Exception:  # noqa: BLE001 - log context then re-raise
        logger.exception("DashScope Generation.call failed (model=%s)", model)
        raise

    status_code = getattr(response, "status_code", HTTPStatus.OK)
    if status_code != HTTPStatus.OK:
        code = getattr(response, "code", None)
        message = getattr(response, "message", None)
        logger.error(
            "DashScope returned non-OK status %s (code=%s): %s",
            status_code,
            code,
            message,
        )
        raise RuntimeError(
            f"DashScope call failed with status {status_code} "
            f"(code={code}): {message}"
        )

    return response


def _parse_structured_output(response: Any) -> dict[str, Any]:
    """Extract a JSON object from a DashScope structured-output response."""

    output = getattr(response, "output", None)
    if output is None:
        raise RuntimeError("DashScope structured response missing output")

    if isinstance(output, dict):
        if isinstance(output.get("text"), dict):
            return output["text"]
        choices = output.get("choices") or []
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content")
            if isinstance(content, dict):
                return content
            if isinstance(content, str) and content.strip():
                return json.loads(content)

    choices = getattr(output, "choices", None)
    if choices:
        message = choices[0].message
        content = message.get("content") if isinstance(message, dict) else message.content
        if isinstance(content, dict):
            return content
        if isinstance(content, str) and content.strip():
            return json.loads(content)

    raise RuntimeError("Unable to parse structured JSON from DashScope response")


async def call_qwen_structured(
    messages: list[dict[str, Any]],
    json_schema: dict[str, Any],
    model: str = "qwen-plus",
) -> dict[str, Any]:
    """Call Qwen with strict JSON schema output and return the parsed object.

    Uses DashScope ``Generation.call`` with ``result_format="json"`` and the
    provided ``json_schema``. The international base URL is applied via
    :func:`get_dashscope_client` when configured.
    """

    client = get_dashscope_client()

    def _invoke() -> Any:
        return client.Generation.call(
            model=model,
            messages=messages,
            result_format="json",
            json_schema=json_schema,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "structured_output",
                    "schema": json_schema,
                    "strict": True,
                },
            },
        )

    try:
        response = await asyncio.to_thread(_invoke)
    except Exception:  # noqa: BLE001 - log context then re-raise
        logger.exception(
            "DashScope Generation.call (structured) failed (model=%s)", model
        )
        raise

    status_code = getattr(response, "status_code", HTTPStatus.OK)
    if status_code != HTTPStatus.OK:
        code = getattr(response, "code", None)
        message = getattr(response, "message", None)
        logger.error(
            "DashScope structured call returned non-OK status %s (code=%s): %s",
            status_code,
            code,
            message,
        )
        raise RuntimeError(
            f"DashScope structured call failed with status {status_code} "
            f"(code={code}): {message}"
        )

    try:
        return _parse_structured_output(response)
    except Exception as exc:
        logger.exception("Failed to parse structured DashScope response")
        raise RuntimeError("Failed to parse structured DashScope response") from exc


async def call_qwen_chat(
    messages: list[dict[str, Any]],
    model: str = DEFAULT_MODEL,
) -> str:
    """Call Qwen for a plain text completion and return the message content.

    Awaitable wrapper over the sync ``Generation.call``. Logs and raises
    ``RuntimeError`` on a non-OK status or SDK error.
    """

    client = get_dashscope_client()

    def _invoke() -> Any:
        return client.Generation.call(
            model=model,
            messages=messages,
            result_format="message",
        )

    try:
        response = await asyncio.to_thread(_invoke)
    except Exception:  # noqa: BLE001 - log context then re-raise
        logger.exception("DashScope Generation.call (chat) failed (model=%s)", model)
        raise

    status_code = getattr(response, "status_code", HTTPStatus.OK)
    if status_code != HTTPStatus.OK:
        code = getattr(response, "code", None)
        message = getattr(response, "message", None)
        logger.error(
            "DashScope chat returned non-OK status %s (code=%s): %s",
            status_code,
            code,
            message,
        )
        raise RuntimeError(
            f"DashScope chat failed with status {status_code} "
            f"(code={code}): {message}"
        )

    return response.output["choices"][0]["message"]["content"]


async def stream_qwen_chat(
    messages: list[dict[str, Any]],
    model: str = DEFAULT_MODEL,
) -> AsyncIterator[str]:
    """Stream Qwen chat tokens as they arrive from DashScope."""

    client = get_dashscope_client()
    token_queue: queue.Queue[tuple[str, Any]] = queue.Queue()
    loop = asyncio.get_running_loop()

    def _producer() -> None:
        try:
            responses = client.Generation.call(
                model=model,
                messages=messages,
                result_format="message",
                stream=True,
                incremental_output=True,
            )
            for response in responses:
                status_code = getattr(response, "status_code", HTTPStatus.OK)
                if status_code != HTTPStatus.OK:
                    loop.call_soon_threadsafe(
                        token_queue.put_nowait, ("error", response)
                    )
                    return
                output = getattr(response, "output", None) or {}
                choices = (
                    output.get("choices")
                    if isinstance(output, dict)
                    else getattr(output, "choices", None)
                )
                if not choices:
                    continue
                choice = choices[0]
                message = (
                    choice.get("message")
                    if isinstance(choice, dict)
                    else getattr(choice, "message", None)
                )
                content = None
                if isinstance(message, dict):
                    content = message.get("content")
                elif message is not None:
                    content = getattr(message, "content", None)
                if content:
                    loop.call_soon_threadsafe(
                        token_queue.put_nowait, ("token", content)
                    )
            loop.call_soon_threadsafe(token_queue.put_nowait, ("done", None))
        except Exception as exc:  # noqa: BLE001
            loop.call_soon_threadsafe(token_queue.put_nowait, ("error", exc))

    threading.Thread(target=_producer, daemon=True).start()

    while True:
        kind, payload = await asyncio.to_thread(token_queue.get)
        if kind == "token":
            yield str(payload)
        elif kind == "done":
            break
        elif kind == "error":
            if isinstance(payload, Exception):
                logger.exception("DashScope streaming failed (model=%s)", model)
                raise RuntimeError("DashScope streaming failed") from payload
            code = getattr(payload, "code", None)
            message = getattr(payload, "message", None)
            status_code = getattr(payload, "status_code", None)
            raise RuntimeError(
                f"DashScope streaming failed with status {status_code} "
                f"(code={code}): {message}"
            )


async def get_embedding(
    text_input: str,
    model: str = DEFAULT_EMBEDDING_MODEL,
) -> list[float]:
    """Return the embedding vector for ``text_input`` using DashScope.

    Wraps the synchronous ``TextEmbedding.call`` in a worker thread. Logs and
    raises ``RuntimeError`` on a non-OK status or SDK error.
    """

    client = get_dashscope_client()

    def _invoke() -> Any:
        return client.TextEmbedding.call(model=model, input=text_input)

    try:
        response = await asyncio.to_thread(_invoke)
    except Exception:  # noqa: BLE001 - log context then re-raise
        logger.exception("DashScope TextEmbedding.call failed (model=%s)", model)
        raise

    status_code = getattr(response, "status_code", HTTPStatus.OK)
    if status_code != HTTPStatus.OK:
        code = getattr(response, "code", None)
        message = getattr(response, "message", None)
        logger.error(
            "DashScope embedding returned non-OK status %s (code=%s): %s",
            status_code,
            code,
            message,
        )
        raise RuntimeError(
            f"DashScope embedding failed with status {status_code} "
            f"(code={code}): {message}"
        )

    return response.output["embeddings"][0]["embedding"]


def _dashscope_status_ok(response: Any) -> bool:
    status_code = getattr(response, "status_code", HTTPStatus.OK)
    return status_code == HTTPStatus.OK


def _raise_dashscope_error(response: Any, label: str) -> None:
    code = getattr(response, "code", None)
    message = getattr(response, "message", None)
    status_code = getattr(response, "status_code", None)
    logger.error(
        "DashScope %s returned non-OK status %s (code=%s): %s",
        label,
        status_code,
        code,
        message,
    )
    raise RuntimeError(
        f"DashScope {label} failed with status {status_code} "
        f"(code={code}): {message}"
    )


def _extract_image_url(response: Any) -> str:
    output = getattr(response, "output", None) or {}
    results = output.get("results") if isinstance(output, dict) else getattr(output, "results", None)
    if not results:
        raise RuntimeError("DashScope image response missing results")

    first = results[0]
    url = first.get("url") if isinstance(first, dict) else getattr(first, "url", None)
    if not url and hasattr(first, "get"):
        url = first.get("url")
    if not url:
        raise RuntimeError("DashScope image response missing url")
    return url


def _extract_video_url(response: Any) -> str:
    output = getattr(response, "output", None) or {}
    url = output.get("video_url") if isinstance(output, dict) else getattr(output, "video_url", None)
    if not url:
        raise RuntimeError("DashScope video response missing video_url")
    return url


async def generate_image(
    prompt: str,
    model: str = IMAGE_MODEL,
    size: str = IMAGE_DEFAULT_SIZE,
) -> str:
    """Generate an image and return its URL (DashScope default size)."""

    from dashscope import ImageSynthesis

    get_dashscope_client()

    def _invoke() -> Any:
        response = ImageSynthesis.call(
            model=model,
            prompt=prompt,
            n=1,
            size=size,
        )
        if not _dashscope_status_ok(response):
            return response

        output = getattr(response, "output", None) or {}
        if isinstance(output, dict) and output.get("task_status") == "FAILED":
            return response

        try:
            return _extract_image_url(response)
        except RuntimeError:
            waited = ImageSynthesis.wait(response)
            if not _dashscope_status_ok(waited):
                return waited
            return _extract_image_url(waited)

    try:
        result = await asyncio.to_thread(_invoke)
    except Exception:  # noqa: BLE001
        logger.exception("DashScope ImageSynthesis failed (model=%s)", model)
        raise

    if isinstance(result, str):
        return result

    if not _dashscope_status_ok(result):
        _raise_dashscope_error(result, "image synthesis")
    return _extract_image_url(result)


async def generate_video(
    prompt: str,
    model: str = VIDEO_MODEL,
    duration: int = VIDEO_DEFAULT_DURATION,
) -> str:
    """Generate a video and return its URL (DashScope default duration)."""

    from dashscope import VideoSynthesis

    get_dashscope_client()

    def _invoke() -> Any:
        task = VideoSynthesis.async_call(
            model=model,
            prompt=prompt,
            duration=duration,
        )
        if not _dashscope_status_ok(task):
            return task
        result = VideoSynthesis.wait(task)
        return result

    try:
        response = await asyncio.to_thread(_invoke)
    except Exception:  # noqa: BLE001
        logger.exception("DashScope VideoSynthesis failed (model=%s)", model)
        raise

    if not _dashscope_status_ok(response):
        _raise_dashscope_error(response, "video synthesis")
    return _extract_video_url(response)


async def synthesize_speech(
    text: str,
    model: str = TTS_MODEL,
    voice: str = TTS_VOICE,
) -> str:
    """Synthesize speech via Qwen-TTS and return an audio URL for ``<audio src>``."""

    from dashscope import MultiModalConversation

    get_dashscope_client()

    def _invoke() -> Any:
        return MultiModalConversation.call(
            model=model,
            text=text,
            voice=voice,
        )

    try:
        response = await asyncio.to_thread(_invoke)
    except Exception:  # noqa: BLE001
        logger.exception("DashScope Qwen-TTS failed (model=%s)", model)
        raise

    if not _dashscope_status_ok(response):
        _raise_dashscope_error(response, "speech synthesis")

    output = getattr(response, "output", None) or {}
    audio = output.get("audio") if isinstance(output, dict) else None
    url = None
    if isinstance(audio, dict):
        url = audio.get("url")
    elif audio is not None:
        url = getattr(audio, "url", None)
    if not url:
        raise RuntimeError("DashScope TTS response missing audio url")
    return url
