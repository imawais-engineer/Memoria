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
async def test_chat_accepts_model_field(client: AsyncClient):
    with patch(
        "app.api.chat.handle_message",
        new=AsyncMock(return_value={"reply": "ok", "session_id": "s1", "memory_ids": []}),
    ) as mock_handle:
        res = await client.post(
            "/chat",
            json={
                "user_id": str(uuid.uuid4()),
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
                video_count=2,
                max_videos=2,
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
async def test_two_videos_then_third_returns_429(client: AsyncClient, db_session_factory):
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
        for i in range(2):
            res = await client.post(
                "/api/generate/video",
                json={"user_id": str(user_id), "prompt": f"video {i}"},
            )
            assert res.status_code == 200, res.text

        third = await client.post(
            "/api/generate/video",
            json={"user_id": str(user_id), "prompt": "one too many"},
        )
    assert third.status_code == 429


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
