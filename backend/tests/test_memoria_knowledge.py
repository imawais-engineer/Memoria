"""Tests for the Memoria product knowledge base."""

from app.services.memoria_knowledge import MEMORIA_KNOWLEDGE_BASE


def test_knowledge_base_covers_core_topics():
    text = MEMORIA_KNOWLEDGE_BASE.lower()
    for topic in (
        "personal intelligence",
        "memoryless",
        "pgvector",
        "celery",
        "slash commands",
        "mcp",
        "consolidation",
        "tasks_list",
        "qwen cloud",
    ):
        assert topic in text, f"missing topic: {topic}"


def test_knowledge_base_includes_memory_types():
    for mem_type in ("core", "episodic", "semantic", "procedural", "goal", "preference"):
        assert mem_type in MEMORIA_KNOWLEDGE_BASE
