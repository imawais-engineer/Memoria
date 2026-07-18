"""Tests for multimodal usage limits and generation endpoints."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.models.user import User


@pytest.mark.asyncio
async def test_list_models(client: AsyncClient):
    res = await client.get("/api/models")
    assert res.status_code == 200
    models = res.json()
    ids = {item["id"] for item in models}
    assert ids == {"qwen-plus", "qwen-max", "qwq-plus", "qwen-turbo"}


@pytest.mark.asyncio
async def test_slash_only_returns_static_help(client: AsyncClient, db_session_factory):
    user_id = uuid.uuid4()
    session_id = str(uuid.uuid4())
    async with db_session_factory() as db:
        db.add(
            User(
                id=user_id,
                username=f"slash_{user_id.hex[:8]}",
                first_name="Test",
                last_name="User",
                favorite_book="Dune",
            )
        )
        await db.commit()

    with patch(
        "app.api.chat.handle_message",
        new=AsyncMock(
            return_value={
                "reply": (
                    "Available commands:\n\n"
                    "/imagine <prompt> – Generate an image\n"
                    "/gen_video <prompt> – Generate a video\n"
                    "/gen_voice <prompt> – Create a voice overview of the conversation"
                ),
                "session_id": session_id,
                "memory_ids": [],
                "title": None,
            }
        ),
    ) as mock_handle:
        res = await client.post(
            "/chat",
            json={
                "user_id": str(user_id),
                "message": "/",
                "session_id": session_id,
            },
        )

    assert res.status_code == 200
    payload = res.json()
    assert payload["memory_ids"] == []
    assert payload["session_id"] == session_id
    assert "/imagine" in payload["reply"]
    assert "/gen_video" in payload["reply"]
    assert "/gen_voice" in payload["reply"]
    mock_handle.assert_awaited_once()
    assert mock_handle.await_args.args[1] == "/"


@pytest.mark.asyncio
async def test_chat_returns_title_when_provided(client: AsyncClient, db_session_factory):
    user_id = uuid.uuid4()
    async with db_session_factory() as db:
        db.add(
            User(
                id=user_id,
                username=f"title_{user_id.hex[:8]}",
                first_name="Test",
                last_name="User",
                favorite_book="Dune",
            )
        )
        await db.commit()

    with patch(
        "app.api.chat.handle_message",
        new=AsyncMock(
            return_value={
                "reply": "Hello!",
                "session_id": "s1",
                "memory_ids": [],
                "title": "Istanbul Trip Planning",
            }
        ),
    ):
        res = await client.post(
            "/chat",
            json={
                "user_id": str(user_id),
                "message": "I am planning a trip to Istanbul",
            },
        )

    assert res.status_code == 200
    assert res.json()["title"] == "Istanbul Trip Planning"


@pytest.mark.asyncio
async def test_chat_accepts_model_field(client: AsyncClient, db_session_factory):
    user_id = uuid.uuid4()
    async with db_session_factory() as db:
        db.add(
            User(
                id=user_id,
                username=f"model_{user_id.hex[:8]}",
                first_name="Test",
                last_name="User",
                favorite_book="Dune",
            )
        )
        await db.commit()

    with patch(
        "app.api.chat.handle_message",
        new=AsyncMock(return_value={"reply": "ok", "session_id": "s1", "memory_ids": []}),
    ) as mock_handle:
        res = await client.post(
            "/chat",
            json={
                "user_id": str(user_id),
                "message": "hello",
                "model": "qwq-plus",
            },
        )
        assert res.status_code == 200
        mock_handle.assert_awaited_once()
        assert mock_handle.await_args.kwargs["model"] == "qwq-plus"


@pytest.mark.asyncio
async def test_image_limit_returns_429(client: AsyncClient, db_session_factory):
    user_id = uuid.uuid4()
    async with db_session_factory() as db:
        db.add(
            User(
                id=user_id,
                username=f"test_{user_id.hex[:8]}",
                first_name="Test",
                last_name="User",
                favorite_book="Dune",
                image_count=5,
                max_images=5,
            )
        )
        await db.commit()

    with patch("app.api.generate.generate_image", new=AsyncMock()):
        res = await client.post(
            "/api/generate/image",
            json={"user_id": str(user_id), "prompt": "a cat"},
        )
    assert res.status_code == 429


@pytest.mark.asyncio
async def test_video_limit_returns_429(client: AsyncClient, db_session_factory):
    user_id = uuid.uuid4()
    async with db_session_factory() as db:
        db.add(
            User(
                id=user_id,
                username=f"vid_{user_id.hex[:8]}",
                first_name="Test",
                last_name="User",
                favorite_book="Dune",
                video_count=5,
                max_videos=5,
            )
        )
        await db.commit()

    with patch("app.api.generate.generate_video", new=AsyncMock()):
        res = await client.post(
            "/api/generate/video",
            json={"user_id": str(user_id), "prompt": "ocean waves"},
        )
    assert res.status_code == 429


@pytest.mark.asyncio
async def test_five_images_then_sixth_returns_429(client: AsyncClient, db_session_factory):
    user_id = uuid.uuid4()
    async with db_session_factory() as db:
        db.add(
            User(
                id=user_id,
                username=f"five_{user_id.hex[:8]}",
                first_name="Test",
                last_name="User",
                favorite_book="Dune",
            )
        )
        await db.commit()

    fake_url = "https://example.com/image.png"
    with patch(
        "app.api.generate.generate_image",
        new=AsyncMock(return_value=fake_url),
    ):
        for i in range(5):
            res = await client.post(
                "/api/generate/image",
                json={"user_id": str(user_id), "prompt": f"image {i}"},
            )
            assert res.status_code == 200, res.text

        sixth = await client.post(
            "/api/generate/image",
            json={"user_id": str(user_id), "prompt": "one too many"},
        )
    assert sixth.status_code == 429


@pytest.mark.asyncio
async def test_five_videos_then_sixth_returns_429(client: AsyncClient, db_session_factory):
    user_id = uuid.uuid4()
    async with db_session_factory() as db:
        db.add(
            User(
                id=user_id,
                username=f"vid2_{user_id.hex[:8]}",
                first_name="Test",
                last_name="User",
                favorite_book="Dune",
            )
        )
        await db.commit()

    fake_url = "https://example.com/video.mp4"
    with patch(
        "app.api.generate.generate_video",
        new=AsyncMock(return_value=fake_url),
    ):
        for i in range(5):
            res = await client.post(
                "/api/generate/video",
                json={"user_id": str(user_id), "prompt": f"video {i}"},
            )
            assert res.status_code == 200, res.text

        sixth = await client.post(
            "/api/generate/video",
            json={"user_id": str(user_id), "prompt": "one too many"},
        )
    assert sixth.status_code == 429


@pytest.mark.asyncio
async def test_voice_generation_returns_overview_and_audio(
    client: AsyncClient,
    db_session_factory,
):
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    async with db_session_factory() as db:
        db.add(
            User(
                id=user_id,
                username=f"voice_{user_id.hex[:8]}",
                first_name="Test",
                last_name="User",
                favorite_book="Dune",
            )
        )
        await db.commit()

    fake_overview = "You discussed memory tiers and LaTeX rendering."
    fake_audio = "data:audio/wav;base64,AAAA"

    with (
        patch(
            "app.api.generate.generate_voice_overview",
            new=AsyncMock(
                return_value={
                    "overview_text": fake_overview,
                    "audio_data_uri": fake_audio,
                }
            ),
        ),
        patch(
            "app.api.sessions.generate_session_title",
            new=AsyncMock(return_value="Voice: create an overview of this discussion"),
        ),
    ):
        res = await client.post(
            "/api/generate/voice",
            json={
                "user_id": str(user_id),
                "session_id": str(session_id),
                "prompt": "create an overview of this discussion",
            },
        )

    assert res.status_code == 200
    payload = res.json()
    assert payload["overview_text"] == fake_overview
    assert payload["audio_data_uri"] == fake_audio
    assert payload["title"] == "Voice: create an overview of this discussion"

    assets_res = await client.get("/api/generate/assets", params={"user_id": str(user_id)})
    assert assets_res.status_code == 200
    assets_payload = assets_res.json()
    assert assets_payload["usage"]["audio_count"] == 1
    assert len(assets_payload["assets"]) == 1
    assert assets_payload["assets"][0]["type"] == "audio"
    assert assets_payload["assets"][0]["url"] == fake_audio


@pytest.mark.asyncio
async def test_message_limit_returns_429(client: AsyncClient, db_session_factory):
    user_id = uuid.uuid4()
    async with db_session_factory() as db:
        db.add(
            User(
                id=user_id,
                username=f"msg_{user_id.hex[:8]}",
                first_name="Test",
                last_name="User",
                favorite_book="Dune",
                message_count=20,
                max_messages=20,
            )
        )
        await db.commit()

    with patch(
        "app.api.chat.handle_message",
        new=AsyncMock(return_value={"reply": "ok", "session_id": "s1", "memory_ids": []}),
    ):
        res = await client.post(
            "/chat",
            json={"user_id": str(user_id), "message": "hello"},
        )
    assert res.status_code == 429


@pytest.mark.asyncio
async def test_audio_limit_returns_429(client: AsyncClient, db_session_factory):
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    async with db_session_factory() as db:
        db.add(
            User(
                id=user_id,
                username=f"aud_{user_id.hex[:8]}",
                first_name="Test",
                last_name="User",
                favorite_book="Dune",
                audio_count=5,
                max_audio=5,
            )
        )
        await db.commit()

    with patch(
        "app.api.generate.generate_voice_overview",
        new=AsyncMock(return_value={"overview_text": "x", "audio_data_uri": "data:audio/wav"}),
    ):
        res = await client.post(
            "/api/generate/voice",
            json={
                "user_id": str(user_id),
                "session_id": str(session_id),
                "prompt": "overview",
            },
        )
    assert res.status_code == 429


@pytest.mark.asyncio
async def test_image_generation_increments_and_stores_asset(
    client: AsyncClient,
    db_session_factory,
):
    user_id = uuid.uuid4()
    async with db_session_factory() as db:
        db.add(
            User(
                id=user_id,
                username=f"img_{user_id.hex[:8]}",
                first_name="Test",
                last_name="User",
                favorite_book="Dune",
            )
        )
        await db.commit()

    fake_url = "https://example.com/image.png"
    with patch(
        "app.api.generate.generate_image",
        new=AsyncMock(return_value=fake_url),
    ):
        res = await client.post(
            "/api/generate/image",
            json={"user_id": str(user_id), "prompt": "purple brain"},
        )
    assert res.status_code == 200
    assert res.json()["url"] == fake_url

    assets_res = await client.get("/api/generate/assets", params={"user_id": str(user_id)})
    assert assets_res.status_code == 200
    payload = assets_res.json()
    assert payload["usage"]["image_count"] == 1
    assert len(payload["assets"]) == 1
    assert payload["assets"][0]["url"] == fake_url
