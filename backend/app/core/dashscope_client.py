"""DashScope (Qwen) client helpers.

Provides a configured DashScope handle and an awaitable wrapper around Qwen
function/tool calling for use by the memory ingestion pipeline.

The DashScope SDK's ``Generation.call`` is synchronous and network-bound, so we
run it in a worker thread via ``asyncio.to_thread`` to keep the async event loop
responsive.
"""

from __future__ import annotations

import asyncio
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
