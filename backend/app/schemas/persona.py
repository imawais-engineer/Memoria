"""Persona defaults and prompt formatting for chat personalization."""

from __future__ import annotations

DEFAULT_PERSONA: dict[str, str | None] = {
    "response_length": "balanced",
    "tone": "professional",
    "behavior": "cautious",
    "custom_tone": None,
    "custom_behavior": None,
}

RESPONSE_LENGTHS = ("concise", "balanced", "detailed")
TONES = ("professional", "friendly", "educational", "witty", "custom")
BEHAVIORS = ("cautious", "encouraging", "direct", "custom")


def normalize_persona(persona: dict | None) -> dict[str, str | None]:
    """Merge stored persona with defaults and normalize optional custom fields."""

    merged = {**DEFAULT_PERSONA, **(persona or {})}
    if merged.get("tone") != "custom":
        merged["custom_tone"] = None
    if merged.get("behavior") != "custom":
        merged["custom_behavior"] = None
    return merged


def format_persona_prompt(persona: dict | None) -> str:
    """Build the persona instruction block for the chat system prompt."""

    data = normalize_persona(persona)
    tone = data["custom_tone"] if data["tone"] == "custom" else data["tone"]
    behavior = (
        data["custom_behavior"] if data["behavior"] == "custom" else data["behavior"]
    )

    block = (
        f"Your persona: You are {data['response_length']} in length, "
        f"{tone} in tone, and {behavior} in advice."
    )

    extras: list[str] = []
    if data["tone"] == "custom" and data.get("custom_tone"):
        extras.append(f"Custom tone guidance: {data['custom_tone']}")
    if data["behavior"] == "custom" and data.get("custom_behavior"):
        extras.append(f"Custom behavior guidance: {data['custom_behavior']}")
    if extras:
        block += " " + " ".join(extras)

    return block
