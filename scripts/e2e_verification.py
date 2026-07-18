#!/usr/bin/env python3
"""End-to-end verification for Memoria against a running backend.

Usage:
    cd backend && alembic upgrade head
    uvicorn app.main:app --port 8000   # separate terminal
    python scripts/e2e_verification.py

Requires PostgreSQL, Redis, and the API server. Set DATABASE_URL in the
environment (or repo-root .env) for quota setup helpers. Media generation
steps call DashScope when DASHSCOPE_API_KEY is set; otherwise they are skipped.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
import uuid
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

BASE_URL = os.getenv("MEMORIA_BASE_URL", "http://localhost:8000")
DEMO_TOKEN = os.getenv("DEMO_API_TOKEN", "memoria-demo-token")
DASHSCOPE_KEY = os.getenv("DASHSCOPE_API_KEY", "")

passed: list[str] = []
failed: list[str] = []
skipped: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        passed.append(name)
        print(f"  PASS  {name}")
    else:
        failed.append(name)
        msg = f"  FAIL  {name}"
        if detail:
            msg += f" — {detail}"
        print(msg)


def skip(name: str, reason: str) -> None:
    skipped.append(name)
    print(f"  SKIP  {name} — {reason}")


def _sync_sql(query: str, params: dict | None = None) -> None:
    from sqlalchemy import create_engine, text

    url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://user:pass@localhost/memoria",
    )
    sync_url = url.replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(sync_url)
    with engine.begin() as conn:
        conn.execute(text(query), params or {})


async def _wait_for_memories(
    client: httpx.AsyncClient, user_id: str, timeout: float = 20.0
) -> list[dict]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        res = await client.get("/api/memories", params={"user_id": user_id})
        if res.status_code == 200:
            data = res.json()
            if data:
                return data
        await asyncio.sleep(2)
    return []


async def run() -> int:
    print(f"\nMemoria E2E verification → {BASE_URL}\n")

    try:
        health = httpx.get(f"{BASE_URL}/health", timeout=10.0)
        check("Backend health", health.status_code == 200, health.text)
    except Exception as exc:  # noqa: BLE001
        check("Backend health", False, str(exc))
        print("\nStart the backend: cd backend && uvicorn app.main:app --port 8000")
        return 1

    username = f"e2e_{uuid.uuid4().hex[:8]}"
    user_id: str | None = None
    session1: str | None = None
    session2: str | None = None
    memory_id: str | None = None
    task_id: str | None = None

    async with httpx.AsyncClient(
        base_url=BASE_URL, timeout=httpx.Timeout(300.0, connect=30.0)
    ) as client:
        # a) Sign up
        signup = await client.post(
            "/auth/signup",
            json={
                "username": username,
                "first_name": "E2E",
                "last_name": "Tester",
                "favorite_book": "Dune",
            },
        )
        check("Signup", signup.status_code == 200, signup.text)
        if signup.status_code == 200:
            user_id = signup.json()["user_id"]

        if not user_id:
            _print_summary()
            return 1

        session1 = str(uuid.uuid4())

        # b) Chat with personal facts
        chat1 = await client.post(
            "/chat",
            json={
                "user_id": user_id,
                "message": "My name is E2E, I'm vegetarian.",
                "session_id": session1,
            },
        )
        check(
            "Chat session 1 (personal facts)",
            chat1.status_code == 200,
            chat1.text,
        )

        # c) Memories from chat (best-effort; Celery may be required)
        memories = await _wait_for_memories(client, user_id, timeout=12.0)
        if memories:
            check(
                "Memories created from chat",
                any("vegetarian" in m.get("content", "").lower() for m in memories),
                f"found {len(memories)} memories",
            )
        else:
            skip(
                "Memories created from chat",
                "no memories after 12s (start Celery worker for extraction)",
            )

        # d) PI off — episodic memory from session 1 should not recall in session 2
        session2 = str(uuid.uuid4())
        await client.patch(
            "/auth/preferences",
            json={"user_id": user_id, "global_memory_enabled": False},
        )
        chat_pi_off = await client.post(
            "/chat",
            json={
                "user_id": user_id,
                "message": "Do I eat meat? Answer briefly.",
                "session_id": session2,
            },
        )
        if chat_pi_off.status_code == 200:
            payload = chat_pi_off.json()
            reply_lower = payload.get("reply", "").lower()
            recalled = "vegetarian" in reply_lower or "do not eat meat" in reply_lower
            session1_memory_ids = {
                m["id"]
                for m in memories
                if m.get("session_id") == session1
            }
            leaked_ids = [
                mid
                for mid in payload.get("memory_ids", [])
                if mid in session1_memory_ids
            ]
            check(
                "PI off limits cross-session recall",
                not leaked_ids and (not recalled or not memories),
                f"leaked memory_ids={leaked_ids}, reply snippet: {payload.get('reply', '')[:120]}",
            )
        else:
            check("PI off chat", False, chat_pi_off.text)

        # e) PI on — recall should work when memories exist
        await client.patch(
            "/auth/preferences",
            json={"user_id": user_id, "global_memory_enabled": True},
        )
        chat_pi_on = await client.post(
            "/chat",
            json={
                "user_id": user_id,
                "message": "What do you know about my diet?",
                "session_id": session2,
            },
        )
        if chat_pi_on.status_code == 200 and memories:
            payload = chat_pi_on.json()
            check(
                "PI on enables memory recall",
                len(payload.get("memory_ids", [])) > 0
                or "vegetarian" in payload.get("reply", "").lower(),
                "",
            )
        elif not memories:
            skip("PI on enables memory recall", "no memories available to recall")
        else:
            check("PI on chat", False, chat_pi_on.text)

        # f) Image limit
        if DASHSCOPE_KEY:
            for i in range(5):
                img = await client.post(
                    "/api/generate/image",
                    json={"user_id": user_id, "prompt": f"e2e test image {i}"},
                )
                if img.status_code != 200:
                    break
            assets = await client.get(
                "/api/generate/assets", params={"user_id": user_id}
            )
            usage = assets.json().get("usage", {}) if assets.status_code == 200 else {}
            check(
                "Image generation (up to 5)",
                usage.get("image_count", 0) >= 1,
                f"image_count={usage.get('image_count')}",
            )
            sixth = await client.post(
                "/api/generate/image",
                json={"user_id": user_id, "prompt": "one too many"},
            )
            check("6th image returns 429", sixth.status_code == 429, sixth.text)
        else:
            _sync_sql(
                "UPDATE users SET image_count = 5, max_images = 5 WHERE id = :id",
                {"id": user_id},
            )
            blocked = await client.post(
                "/api/generate/image",
                json={"user_id": user_id, "prompt": "blocked"},
            )
            check(
                "Image limit 429 (quota preset)",
                blocked.status_code == 429,
                blocked.text,
            )
            skip("Image generation live", "DASHSCOPE_API_KEY not set")

        # g) Video limit
        _sync_sql(
            "UPDATE users SET video_count = 0, max_videos = 2 WHERE id = :id",
            {"id": user_id},
        )
        if DASHSCOPE_KEY:
            for i in range(2):
                await client.post(
                    "/api/generate/video",
                    json={"user_id": user_id, "prompt": f"e2e video {i}"},
                )
            third = await client.post(
                "/api/generate/video",
                json={"user_id": user_id, "prompt": "one too many"},
            )
            check("3rd video returns 429", third.status_code == 429, third.text)
        else:
            _sync_sql(
                "UPDATE users SET video_count = 2, max_videos = 2 WHERE id = :id",
                {"id": user_id},
            )
            blocked = await client.post(
                "/api/generate/video",
                json={"user_id": user_id, "prompt": "blocked"},
            )
            check(
                "Video limit 429 (quota preset)",
                blocked.status_code == 429,
                blocked.text,
            )
            skip("Video generation live", "DASHSCOPE_API_KEY not set")

        # h) Audio / voice limit
        _sync_sql(
            "UPDATE users SET audio_count = 0, max_audio = 2 WHERE id = :id",
            {"id": user_id},
        )
        voice_session = str(uuid.uuid4())
        if DASHSCOPE_KEY:
            for i in range(2):
                await client.post(
                    "/api/generate/voice",
                    json={
                        "user_id": user_id,
                        "session_id": voice_session,
                        "prompt": f"overview {i}",
                    },
                )
            third_voice = await client.post(
                "/api/generate/voice",
                json={
                    "user_id": user_id,
                    "session_id": voice_session,
                    "prompt": "one too many",
                },
            )
            check(
                "3rd voice returns 429",
                third_voice.status_code == 429,
                third_voice.text,
            )
        else:
            _sync_sql(
                "UPDATE users SET audio_count = 2, max_audio = 2 WHERE id = :id",
                {"id": user_id},
            )
            blocked = await client.post(
                "/api/generate/voice",
                json={
                    "user_id": user_id,
                    "session_id": voice_session,
                    "prompt": "blocked",
                },
            )
            check(
                "Audio limit 429 (quota preset)",
                blocked.status_code == 429,
                blocked.text,
            )
            skip("Voice generation live", "DASHSCOPE_API_KEY not set")

        # i) Memorize
        mem = await client.post(
            "/api/memorize",
            json={
                "user_id": user_id,
                "content": "E2E manual memory: prefers tea over coffee",
            },
        )
        check("Memorize creates memory", mem.status_code == 200, mem.text)
        if mem.status_code == 200:
            memory_id = mem.json().get("id")
        all_memories = await client.get(
            "/api/memories", params={"user_id": user_id}
        )
        check(
            "Memorize appears in memory list",
            all_memories.status_code == 200
            and any(
                "tea over coffee" in m.get("content", "")
                for m in all_memories.json()
            ),
            all_memories.text,
        )

        # j) Tasks via API (chat commands use same endpoints)
        task_create = await client.post(
            "/api/tasks",
            json={"user_id": user_id, "title": "Buy groceries"},
        )
        check("Create task", task_create.status_code == 200, task_create.text)
        if task_create.status_code == 200:
            task_id = task_create.json()["id"]
        tasks_list = await client.get("/api/tasks", params={"user_id": user_id})
        check(
            "List tasks",
            tasks_list.status_code == 200
            and any(t["title"] == "Buy groceries" for t in tasks_list.json()),
            tasks_list.text,
        )
        if task_id:
            done = await client.patch(
                f"/api/tasks/{task_id}",
                json={"status": "completed"},
            )
            check(
                "Mark task complete",
                done.status_code == 200
                and done.json().get("status") == "completed",
                done.text,
            )

        # k) Delete memory
        if memory_id:
            deleted = await client.delete(
                f"/api/memories/{memory_id}",
                params={"user_id": user_id},
                headers={"X-API-Token": DEMO_TOKEN},
            )
            check("Delete memory", deleted.status_code == 200, deleted.text)
            remaining = await client.get(
                "/api/memories", params={"user_id": user_id}
            )
            check(
                "Memory removed after delete",
                remaining.status_code == 200
                and not any(m["id"] == memory_id for m in remaining.json()),
                "",
            )

        # Message limit spot-check
        _sync_sql(
            "UPDATE users SET message_count = 10, max_messages = 10 WHERE id = :id",
            {"id": user_id},
        )
        blocked_msg = await client.post(
            "/chat",
            json={"user_id": user_id, "message": "should be blocked"},
        )
        check(
            "Message limit 429",
            blocked_msg.status_code == 429,
            blocked_msg.text,
        )

    _print_summary()
    return 0 if not failed else 1


def _print_summary() -> None:
    print("\n" + "=" * 60)
    print(f"Passed:  {len(passed)}")
    print(f"Failed:  {len(failed)}")
    print(f"Skipped: {len(skipped)}")
    if failed:
        print("\nFailed checks:")
        for item in failed:
            print(f"  - {item}")
    if skipped:
        print("\nSkipped checks:")
        for item in skipped:
            print(f"  - {item}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    try:
        from dotenv import load_dotenv

        load_dotenv(REPO_ROOT / ".env")
    except ImportError:
        pass
    raise SystemExit(asyncio.run(run()))
