"""Session title helpers: Qwen-generated titles and media slash-command labels."""

from __future__ import annotations

import logging

from app.core.dashscope_client import call_qwen_chat

logger = logging.getLogger(__name__)

MAX_TITLE_LENGTH = 80

SLASH_HELP_REPLY = (
    "📋 **Available Commands**\n\n"
    "| Command | Description | AI Cost |\n"
    "|---------|-------------|--------|\n"
    "| `/imagine <prompt>` | Generate an image | AI |\n"
    "| `/gen_video <prompt>` | Generate a video | AI |\n"
    "| `/gen_voice <prompt>` | Create a voice overview | AI |\n"
    "| `/memorize <fact>` | Store a fact manually | Free |\n"
    "| `/create_task <title>` | Create a task | Free |\n"
    "| `/tasks_list` | List pending tasks | Free |\n"
    "| `/task_complete <ID>` | Mark a task as done | Free |\n"
    "| `/list_memory` | List memories | Free |\n"
    "| `/forget_memory <ID\\|ALL>` | Delete memories | Free |"
)

_MEDIA_PREFIXES: tuple[tuple[str, str], ...] = (
    ("/imagine", "Image"),
    ("/gen_video", "Video"),
    ("/gen_voice", "Voice"),
)


def title_from_slash_message(message: str) -> str | None:
    """Derive a sidebar title from a media slash command, if applicable."""

    trimmed = message.strip()
    for prefix, label in _MEDIA_PREFIXES:
        if trimmed.startswith(prefix):
            prompt = trimmed[len(prefix) :].strip()
            if not prompt:
                return label
            short = prompt if len(prompt) <= 60 else f"{prompt[:57]}…"
            title = f"{label}: {short}"
            return title if len(title) <= MAX_TITLE_LENGTH else title[: MAX_TITLE_LENGTH - 1] + "…"
    return None


def _fallback_title(message: str) -> str:
    cleaned = " ".join(message.strip().split())
    if not cleaned:
        return "New Chat"
    if len(cleaned) <= MAX_TITLE_LENGTH:
        return cleaned
    return cleaned[: MAX_TITLE_LENGTH - 1].rstrip() + "…"


async def generate_session_title(message: str) -> str:
    """Generate a concise session title from the user's first message via Qwen-Plus."""

    cleaned = " ".join(message.strip().split())
    if not cleaned:
        return "New Chat"

    media_title = title_from_slash_message(cleaned)
    if media_title:
        return media_title

    try:
        title = await call_qwen_chat(
            [
                {
                    "role": "system",
                    "content": (
                        "You generate short chat session titles (2–6 words). "
                        "Return ONLY the title text — no quotes, no punctuation wrapper, "
                        "no explanation."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Create a title for a chat that starts with:\n\n{cleaned}",
                },
            ],
            model="qwen-plus",
        )
        title = " ".join(title.strip().split())
        if title:
            if len(title) > MAX_TITLE_LENGTH:
                return title[: MAX_TITLE_LENGTH - 1].rstrip() + "…"
            return title
    except Exception:  # noqa: BLE001
        logger.exception("Qwen session title generation failed; using fallback")

    return _fallback_title(cleaned)
