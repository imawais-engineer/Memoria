#!/usr/bin/env python3
"""Validate all DashScope (Qwen Cloud) models through the unified client.

Run from ``backend/``::

    python scripts/validate_dashscope.py

Requires ``DASHSCOPE_API_KEY``. Uses the international endpoint by default
(see ``app.config.Settings.dashscope_base_url``).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.dashscope_client import (  # noqa: E402
    call_qwen_chat,
    generate_image,
    generate_video,
    get_dashscope_client,
    synthesize_speech,
)
from app.services.voice_generation import generate_voice_overview  # noqa: E402


async def main() -> int:
    get_dashscope_client()
    failures = 0

    async def check(label: str, coro) -> None:
        nonlocal failures
        try:
            result = await coro
            preview = str(result)
            print(f"OK  {label}: {preview[:100]}{'…' if len(preview) > 100 else ''}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"FAIL {label}: {exc}")

    print("DashScope unified validation (Qwen Cloud SDK via dashscope_client.py)\n")

    await check(
        "chat/qwen-plus",
        call_qwen_chat([{"role": "user", "content": "Reply with exactly: Memoria OK"}], model="qwen-plus"),
    )
    await check("image/wan2.1-t2i-plus", generate_image("a small red cube on a white background"))
    await check("video/wan2.1-t2v-turbo", generate_video("a calm ocean wave at sunset"))
    await check("tts/qwen3-tts-flash", synthesize_speech("Memoria voice check."))

    # Voice overview needs Redis session context; skip if Redis unavailable.
    try:
        import redis.asyncio as redis

        from app.config import get_settings

        settings = get_settings()
        redis_client = redis.from_url(settings.redis_url, decode_responses=False)
        await check(
            "voice-overview (qwen-plus + qwen3-tts-flash)",
            generate_voice_overview(
                user_prompt="Summarize this test session.",
                session_id="validate-session",
                redis_client=redis_client,
            ),
        )
        await redis_client.aclose()
    except Exception as exc:  # noqa: BLE001
        print(f"SKIP voice-overview: {exc}")

    print(f"\n{'All checks passed.' if failures == 0 else f'{failures} check(s) failed.'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
