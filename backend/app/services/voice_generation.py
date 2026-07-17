"""Two-step voice overview: session summary via Qwen, then TTS."""

from __future__ import annotations

import json
import logging

import redis.asyncio as redis

from app.core.dashscope_client import call_qwen_chat, synthesize_speech

logger = logging.getLogger(__name__)

OVERVIEW_INSTRUCTION = (
    "Provide ONLY the plain-text overview. Do NOT include introductory phrases "
    "like 'Here is...' or 'Would you like me to...'. Just the overview itself."
)


async def _load_session_transcript(
    redis_client: redis.Redis,
    session_id: str,
) -> str:
    """Return a plain-text transcript of recent session messages from Redis."""

    session_key = f"session:{session_id}"
    raw_history = await redis_client.lrange(session_key, 0, -1)
    lines: list[str] = []
    for item in raw_history:
        try:
            payload = json.loads(item)
            role = payload.get("role")
            content = payload.get("content")
            if role and content is not None:
                label = "User" if role == "user" else "Assistant"
                lines.append(f"{label}: {content}")
        except (json.JSONDecodeError, TypeError):
            continue
    return "\n".join(lines) if lines else "(No prior messages in this session.)"


async def generate_voice_overview(
    *,
    user_prompt: str,
    session_id: str,
    redis_client: redis.Redis,
) -> dict[str, str]:
    """Generate a text overview from session context, then synthesize speech.

    Returns a dict with ``overview_text`` and ``audio_data_uri`` (base64 WAV).
    """

    transcript = await _load_session_transcript(redis_client, session_id)
    messages = [
        {
            "role": "system",
            "content": (
                "You create concise spoken overviews of chat sessions. "
                f"{OVERVIEW_INSTRUCTION}"
            ),
        },
        {
            "role": "user",
            "content": (
                f"Session conversation:\n{transcript}\n\n"
                f"User request: {user_prompt}\n\n"
                f"{OVERVIEW_INSTRUCTION}"
            ),
        },
    ]

    overview_text = await call_qwen_chat(messages, model="qwen-plus")
    overview_text = overview_text.strip()
    if not overview_text:
        raise RuntimeError("Voice overview text generation returned empty content")

    audio_data_uri = await synthesize_speech(overview_text)
    return {
        "overview_text": overview_text,
        "audio_data_uri": audio_data_uri,
    }
