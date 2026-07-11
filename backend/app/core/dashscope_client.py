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
from http import HTTPStatus
from types import ModuleType
from typing import Any

import dashscope

from app.config import get_settings

logger = logging.getLogger(__name__)

# Default Qwen model used for memory extraction / tool calling.
DEFAULT_MODEL = "qwen3-plus"

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
    api_key = settings.dashscope_api_key or os.getenv("DASHSCOPE_API_KEY", "")

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
