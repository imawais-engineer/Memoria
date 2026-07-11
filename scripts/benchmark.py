#!/usr/bin/env python3
"""Benchmark Memoria memory impact on personalized recommendation quality.

Runs twelve scenarios against Qwen-Plus with and without stored user memories,
scores responses on accuracy/safety/coherence, and writes JSON + chart outputs.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt

# Allow imports from the backend package when run from repo root or backend/.
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import delete

from app.core.dashscope_client import call_qwen_chat, get_embedding
from app.core.database import async_session, engine
from app.memory.models import Memory
from app.memory.retrieval import retrieve_context

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("benchmark")

CHAT_MODEL = "qwen-plus"
QWEN_TIMEOUT_SECONDS = 90
BENCHMARK_USER_ID = "benchmark-user"
SCRIPT_DIR = Path(__file__).resolve().parent
RESULTS_JSON = SCRIPT_DIR / "benchmark_results.json"
RESULTS_PNG = SCRIPT_DIR / "benchmark_results.png"

USER_PROFILE: dict[str, Any] = {
    "allergies": ["peanuts", "shellfish"],
    "dietary": "vegetarian",
    "interests": ["hiking", "cooking", "machine learning"],
    "goals": ["eat healthier", "learn Python"],
    "preferences": {
        "likes": ["spicy food"],
        "dislikes": ["bland food"],
        "restaurants": "prefers local restaurants",
    },
}

PROFILE_MEMORY_LINES: list[tuple[str, str]] = [
    ("core", "User is allergic to peanuts and shellfish."),
    ("core", "User follows a vegetarian diet and does not eat meat or fish."),
    (
        "semantic",
        "User enjoys hiking, cooking, and machine learning as hobbies.",
    ),
    ("semantic", "User wants to eat healthier and learn Python."),
    (
        "semantic",
        "User likes spicy food, dislikes bland food, and prefers local restaurants.",
    ),
]

TEST_SCENARIOS: list[str] = [
    "Recommend a restaurant for Friday dinner",
    "Suggest a weekend activity",
    "What should I cook tonight?",
    "Plan a healthy lunch for tomorrow",
    "Recommend a local dinner spot for a date night",
    "What hiking trail should I try this weekend?",
    "Suggest a fun cooking project for Sunday",
    "How can I make progress on learning Python this week?",
    "What machine learning topic should I study next?",
    "Recommend a spicy vegetarian dish I could order",
    "Help me choose a meal prep plan for the week",
    "What should I do on a rainy Saturday that fits my interests?",
]

ALLERGEN_TERMS = (
    "peanut",
    "peanuts",
    "shellfish",
    "shrimp",
    "prawn",
    "prawns",
    "crab",
    "lobster",
    "clam",
    "oyster",
    "mussels",
    "scallop",
)
MEAT_TERMS = (
    "beef",
    "chicken",
    "pork",
    "bacon",
    "ham",
    "steak",
    "burger",
    "meatball",
    "salmon",
    "tuna",
    "fish",
    "seafood",
    "lamb",
    "turkey",
    "sausage",
)
BLAND_TERMS = ("bland", "plain", "unseasoned", "boiled rice only", "no flavor")
SPICY_TERMS = ("spicy", "chili", "chilli", "szechuan", "thai", "curry", "hot sauce")
LOCAL_TERMS = ("local", "neighborhood", "family-owned", "independent", "farmers market")
VEGETARIAN_TERMS = ("vegetarian", "veggie", "plant-based", "tofu", "lentil", "chickpea")
HEALTH_TERMS = ("healthy", "nutritious", "balanced", "whole grain", "vegetables", "salad")
HIKING_TERMS = ("hike", "hiking", "trail", "outdoor", "mountain", "nature walk")
COOKING_TERMS = ("cook", "cooking", "recipe", "kitchen", "bake", "meal")
PYTHON_TERMS = ("python", "coding", "programming", "script", "tutorial", "course")
ML_TERMS = ("machine learning", "ml", "model", "neural", "data science", "deep learning")

FOOD_SCENARIOS = {
    "Recommend a restaurant for Friday dinner",
    "What should I cook tonight?",
    "Plan a healthy lunch for tomorrow",
    "Recommend a local dinner spot for a date night",
    "Recommend a spicy vegetarian dish I could order",
    "Help me choose a meal prep plan for the week",
}
ACTIVITY_SCENARIOS = {
    "Suggest a weekend activity",
    "What hiking trail should I try this weekend?",
    "Suggest a fun cooking project for Sunday",
    "What should I do on a rainy Saturday that fits my interests?",
}
LEARNING_SCENARIOS = {
    "How can I make progress on learning Python this week?",
    "What machine learning topic should I study next?",
}


@dataclass
class ScoreTriple:
    accuracy: float
    safety: float
    coherence: float

    @property
    def average(self) -> float:
        return (self.accuracy + self.safety + self.coherence) / 3.0

    def as_dict(self) -> dict[str, float]:
        return {
            "accuracy": round(self.accuracy, 3),
            "safety": round(self.safety, 3),
            "coherence": round(self.coherence, 3),
        }


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{re.escape(term)}\b", text) for term in terms)


def _is_unsafe_term(text: str, term: str) -> bool:
    """Return True when ``term`` appears as a recommendation, not an avoidance."""

    for match in re.finditer(rf"\b{re.escape(term)}\b", text):
        start = max(0, match.start() - 50)
        window = text[start : match.end() + 20]
        if any(
            cue in window
            for cue in (
                "allerg",
                "avoid",
                "without",
                "free",
                "can't eat",
                "cannot eat",
                "do not",
                "don't",
                "not eat",
                "no ",
            )
        ):
            continue
        return True
    return False


def _unsafe_hits(text: str, terms: tuple[str, ...]) -> int:
    return sum(1 for term in terms if _is_unsafe_term(text, term))


async def judge_response(scenario: str, response: str) -> ScoreTriple:
    """Use Qwen-Plus to score a recommendation against the synthetic profile."""

    profile_text = (
        "Allergies: peanuts, shellfish\n"
        "Diet: vegetarian\n"
        "Interests: hiking, cooking, machine learning\n"
        "Goals: eat healthier, learn Python\n"
        "Preferences: likes spicy food, dislikes bland food, prefers local restaurants"
    )
    messages = [
        {
            "role": "system",
            "content": (
                "You are an impartial evaluator. Score recommendations from 0.0 to 1.0 "
                "for accuracy (profile fit), safety (no allergens/meat violations), and "
                "coherence (preference alignment). Reply with ONLY valid JSON like "
                '{"accuracy": 0.8, "safety": 0.9, "coherence": 0.7}.'
            ),
        },
        {
            "role": "user",
            "content": (
                f"User profile:\n{profile_text}\n\n"
                f"Scenario: {scenario}\n\n"
                f"Recommendation:\n{response}\n\n"
                "Return JSON scores only."
            ),
        },
    ]
    try:
        raw = await asyncio.wait_for(
            call_qwen_chat(messages, model=CHAT_MODEL),
            timeout=QWEN_TIMEOUT_SECONDS,
        )
        match = re.search(r"\{[^{}]+\}", raw)
        if not match:
            raise ValueError("No JSON object in judge response")
        data = json.loads(match.group())
        return ScoreTriple(
            accuracy=float(data.get("accuracy", 0.0)),
            safety=float(data.get("safety", 0.0)),
            coherence=float(data.get("coherence", 0.0)),
        )
    except Exception:
        logger.warning(
            "LLM judge failed for scenario=%s; falling back to heuristic scoring",
            scenario,
            exc_info=True,
        )
        return heuristic_score_response(scenario, response)


def heuristic_score_response(scenario: str, response: str) -> ScoreTriple:
    """Fallback heuristic scorer when the LLM judge is unavailable."""

    text = response.lower()

    safety = 1.0
    safety -= min(1.0, 0.35 * _unsafe_hits(text, ALLERGEN_TERMS))
    if scenario in FOOD_SCENARIOS:
        safety -= min(0.8, 0.25 * _unsafe_hits(text, MEAT_TERMS))
    safety = max(0.0, safety)

    accuracy = 0.35
    if scenario in FOOD_SCENARIOS:
        if _contains_any(text, VEGETARIAN_TERMS):
            accuracy += 0.25
        if _contains_any(text, HEALTH_TERMS):
            accuracy += 0.15
        if _unsafe_hits(text, ALLERGEN_TERMS) == 0:
            accuracy += 0.15
    if scenario in ACTIVITY_SCENARIOS:
        if _contains_any(text, HIKING_TERMS):
            accuracy += 0.25
        if _contains_any(text, COOKING_TERMS):
            accuracy += 0.2
        if _contains_any(text, ML_TERMS):
            accuracy += 0.1
    if scenario in LEARNING_SCENARIOS:
        if _contains_any(text, PYTHON_TERMS):
            accuracy += 0.3
        if _contains_any(text, ML_TERMS):
            accuracy += 0.25
    accuracy = min(1.0, max(0.0, accuracy))

    coherence = 0.35
    if scenario in FOOD_SCENARIOS:
        if _contains_any(text, SPICY_TERMS):
            coherence += 0.25
        if _contains_any(text, LOCAL_TERMS):
            coherence += 0.2
        if not _contains_any(text, BLAND_TERMS):
            coherence += 0.15
        if _contains_any(text, BLAND_TERMS):
            coherence -= 0.25
    if scenario in ACTIVITY_SCENARIOS:
        if _contains_any(text, HIKING_TERMS) or _contains_any(text, COOKING_TERMS):
            coherence += 0.35
    if scenario in LEARNING_SCENARIOS:
        if _contains_any(text, PYTHON_TERMS) or _contains_any(text, ML_TERMS):
            coherence += 0.35
    coherence = min(1.0, max(0.0, coherence))

    return ScoreTriple(accuracy=accuracy, safety=safety, coherence=coherence)


async def seed_profile_memories() -> None:
    """Insert the synthetic profile as embedded memories for the benchmark user."""

    async with async_session() as db:
        await db.execute(delete(Memory).where(Memory.user_id == BENCHMARK_USER_ID))
        now = datetime.now(timezone.utc)
        for mem_type, content in PROFILE_MEMORY_LINES:
            embedding = await get_embedding(content)
            db.add(
                Memory(
                    user_id=BENCHMARK_USER_ID,
                    type=mem_type,
                    content=content,
                    embedding=embedding,
                    importance=0.95 if mem_type == "core" else 0.85,
                    created_at=now,
                    last_accessed=now,
                    decay_rate=0.0 if mem_type == "core" else 0.01,
                    meta_data={"source": "benchmark_profile"},
                )
            )
        await db.commit()
    logger.info("Seeded %d profile memories for %s", len(PROFILE_MEMORY_LINES), BENCHMARK_USER_ID)


async def ask_qwen(scenario: str, memory_context: str | None = None) -> str:
    """Call Qwen-Plus with optional memory context."""

    if memory_context:
        system_prompt = (
            "You are a personal AI with memory. Here is what you know about the "
            f"user: {memory_context}. Use this to personalise responses. "
            "Provide one concise, actionable recommendation."
        )
    else:
        system_prompt = (
            "You are a helpful assistant. Provide one concise, actionable "
            "recommendation."
        )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": scenario},
    ]
    return (
        await asyncio.wait_for(
            call_qwen_chat(messages, model=CHAT_MODEL),
            timeout=QWEN_TIMEOUT_SECONDS,
        )
    ).strip()


def improvement_percent(before: ScoreTriple, after: ScoreTriple) -> float:
    """Return percentage improvement from before to after average score."""

    if before.average <= 0:
        return 100.0 if after.average > 0 else 0.0
    return ((after.average - before.average) / before.average) * 100.0


def format_markdown_table(rows: list[dict[str, Any]], avg_improvement: float) -> str:
    """Build the markdown results table."""

    lines = [
        "| Scenario | Without (Acc/Saf/Coh) | With (Acc/Saf/Coh) | Improvement % |",
        "|---|---|---|---:|",
    ]
    for row in rows:
        without = row["without"]
        with_mem = row["with"]
        lines.append(
            f"| {row['scenario']} | "
            f"{without['accuracy']:.2f}/{without['safety']:.2f}/{without['coherence']:.2f} | "
            f"{with_mem['accuracy']:.2f}/{with_mem['safety']:.2f}/{with_mem['coherence']:.2f} | "
            f"{row['improvement_pct']:.1f}% |"
        )
    lines.append("")
    lines.append(f"**Average improvement:** {avg_improvement:.1f}%")
    return "\n".join(lines)


def save_chart(rows: list[dict[str, Any]]) -> None:
    """Generate a grouped bar chart comparing average before/after scores."""

    if not rows:
        logger.warning("No successful scenarios to chart.")
        return

    metrics = ("accuracy", "safety", "coherence")
    without_avgs = [
        sum(row["without"][metric] for row in rows) / len(rows) for metric in metrics
    ]
    with_avgs = [
        sum(row["with"][metric] for row in rows) / len(rows) for metric in metrics
    ]

    x_labels = ["Accuracy", "Safety", "Coherence"]
    x = range(len(x_labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar([i - width / 2 for i in x], without_avgs, width, label="Without Memory")
    ax.bar([i + width / 2 for i in x], with_avgs, width, label="With Memory")
    ax.set_ylabel("Average Score (0-1)")
    ax.set_title("Memoria Benchmark: Recommendation Quality With vs Without Memory")
    ax.set_xticks(list(x))
    ax.set_xticklabels(x_labels)
    ax.set_ylim(0, 1.05)
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()
    fig.savefig(RESULTS_PNG, dpi=150)
    plt.close(fig)
    logger.info("Saved chart to %s", RESULTS_PNG)


async def run_benchmark() -> dict[str, Any]:
    """Execute the full benchmark suite."""

    await seed_profile_memories()

    result_rows: list[dict[str, Any]] = []

    async with async_session() as db:
        for scenario in TEST_SCENARIOS:
            logger.info("Running scenario: %s", scenario)
            try:
                without_response = await ask_qwen(scenario, memory_context=None)
                without_score = await judge_response(scenario, without_response)

                context = await retrieve_context(
                    BENCHMARK_USER_ID, scenario, db_session=db
                )
                with_response = await ask_qwen(scenario, memory_context=context)
                with_score = await judge_response(scenario, with_response)

                row = {
                    "scenario": scenario,
                    "without": without_score.as_dict(),
                    "with": with_score.as_dict(),
                    "improvement_pct": round(
                        improvement_percent(without_score, with_score), 1
                    ),
                    "without_response": without_response[:500],
                    "with_response": with_response[:500],
                }
                result_rows.append(row)
                logger.info(
                    "Scenario complete: without=%.2f with=%.2f improvement=%.1f%%",
                    without_score.average,
                    with_score.average,
                    row["improvement_pct"],
                )
            except Exception:
                logger.warning(
                    "Skipping scenario due to Qwen/retrieval failure: %s",
                    scenario,
                    exc_info=True,
                )

    if not result_rows:
        raise RuntimeError("All benchmark scenarios failed; no results to report.")

    avg_improvement = sum(row["improvement_pct"] for row in result_rows) / len(
        result_rows
    )
    avg_accuracy_with = sum(row["with"]["accuracy"] for row in result_rows) / len(
        result_rows
    )

    payload = {
        "user_profile": USER_PROFILE,
        "model": CHAT_MODEL,
        "scenarios": [
            {
                "scenario": row["scenario"],
                "without": row["without"],
                "with": row["with"],
                "improvement_pct": row["improvement_pct"],
            }
            for row in result_rows
        ],
        "avg_accuracy": round(avg_accuracy_with, 3),
        "avg_improvement": round(avg_improvement, 1),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    RESULTS_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Saved JSON results to %s", RESULTS_JSON)

    table = format_markdown_table(result_rows, avg_improvement)
    print(table)
    save_chart(result_rows)

    return payload


async def main() -> None:
    try:
        payload = await run_benchmark()
        print(
            f"\nAverage improvement: {payload['avg_improvement']:.1f}% "
            f"(target > 20%)"
        )
        if payload["avg_improvement"] <= 20:
            logger.warning(
                "Average improvement %.1f%% is at or below 20%% target.",
                payload["avg_improvement"],
            )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
