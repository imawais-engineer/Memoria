"""Multimodal generation API: image, video, voice, chat models."""

from __future__ import annotations

import logging
from uuid import UUID

import redis.asyncio as redis
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.sessions import ensure_session_exists, touch_session_on_message
from app.config import get_settings
from app.core.dashscope_client import (
    CHAT_MODELS,
    generate_image,
    generate_video,
)
from app.core.database import get_db
from app.core.redis_client import get_redis
from app.models.generated_asset import GeneratedAsset
from app.services.usage import check_and_increment_usage, get_usage_summary
from app.services.voice_generation import generate_voice_overview

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["generate"])


def require_token(x_api_token: str = Header(default="")) -> None:
    """Simple fixed-token auth for destructive endpoints (demo only)."""

    if x_api_token != get_settings().demo_api_token:
        raise HTTPException(status_code=401, detail="Invalid or missing API token")


class GenerateImageRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    prompt: str = Field(..., min_length=1)
    session_id: str | None = None
    is_memoryless: bool = False


class GenerateVideoRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    prompt: str = Field(..., min_length=1)
    session_id: str | None = None
    is_memoryless: bool = False


class GenerateVoiceRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)
    prompt: str = Field(..., min_length=1)
    is_memoryless: bool = False


class GenerateUrlResponse(BaseModel):
    url: str
    session_id: str | None = None
    title: str | None = None


class GenerateVoiceResponse(BaseModel):
    overview_text: str
    audio_data_uri: str
    title: str | None = None


class GeneratedAssetOut(BaseModel):
    id: str
    user_id: str
    type: str
    prompt: str
    url: str
    created_at: str


class UsageOut(BaseModel):
    message_count: int
    image_count: int
    video_count: int
    audio_count: int
    max_messages: int
    max_images: int
    max_videos: int
    max_audio: int
    messages_remaining: int
    images_remaining: int
    videos_remaining: int
    audio_remaining: int


class AssetsListResponse(BaseModel):
    usage: UsageOut
    assets: list[GeneratedAssetOut]


class ChatModelOut(BaseModel):
    id: str
    name: str


@router.get("/models", response_model=list[ChatModelOut])
async def list_chat_models() -> list[ChatModelOut]:
    """Return chat models available in the model switcher."""

    return [ChatModelOut(**item) for item in CHAT_MODELS]


async def _bind_media_session(
    db: AsyncSession,
    *,
    user_id: str,
    session_id: str | None,
    slash_message: str,
    is_memoryless: bool = False,
) -> str | None:
    if not session_id:
        return None
    await ensure_session_exists(
        session_id,
        user_id,
        is_memoryless=is_memoryless,
        db=db,
    )
    return await touch_session_on_message(session_id, slash_message, db)


@router.post("/generate/image", response_model=GenerateUrlResponse)
async def create_image(
    body: GenerateImageRequest,
    db: AsyncSession = Depends(get_db),
) -> GenerateUrlResponse:
    allowed = await check_and_increment_usage(db, body.user_id, "image")
    if not allowed:
        raise HTTPException(status_code=429, detail="Image generation limit reached")

    session_title = await _bind_media_session(
        db,
        user_id=body.user_id,
        session_id=body.session_id,
        slash_message=f"/imagine {body.prompt}",
        is_memoryless=body.is_memoryless,
    )

    try:
        url = await generate_image(body.prompt)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Image generation failed for user_id=%s", body.user_id)
        raise HTTPException(status_code=500, detail="Image generation failed") from exc

    asset = GeneratedAsset(
        user_id=UUID(body.user_id),
        type="image",
        prompt=body.prompt,
        url=url,
    )
    db.add(asset)
    await db.commit()

    return GenerateUrlResponse(url=url, session_id=body.session_id, title=session_title)


@router.post("/generate/video", response_model=GenerateUrlResponse)
async def create_video(
    body: GenerateVideoRequest,
    db: AsyncSession = Depends(get_db),
) -> GenerateUrlResponse:
    allowed = await check_and_increment_usage(db, body.user_id, "video")
    if not allowed:
        raise HTTPException(status_code=429, detail="Video generation limit reached")

    session_title = await _bind_media_session(
        db,
        user_id=body.user_id,
        session_id=body.session_id,
        slash_message=f"/gen_video {body.prompt}",
        is_memoryless=body.is_memoryless,
    )

    try:
        url = await generate_video(body.prompt)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Video generation failed for user_id=%s", body.user_id)
        raise HTTPException(status_code=500, detail="Video generation failed") from exc

    asset = GeneratedAsset(
        user_id=UUID(body.user_id),
        type="video",
        prompt=body.prompt,
        url=url,
    )
    db.add(asset)
    await db.commit()

    return GenerateUrlResponse(url=url, session_id=body.session_id, title=session_title)


@router.post("/generate/voice", response_model=GenerateVoiceResponse)
async def create_voice(
    body: GenerateVoiceRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
) -> GenerateVoiceResponse:
    """Two-step voice overview: Qwen summary of session context, then TTS."""

    allowed = await check_and_increment_usage(db, body.user_id, "audio")
    if not allowed:
        raise HTTPException(status_code=429, detail="Audio generation limit reached")

    session_title = await _bind_media_session(
        db,
        user_id=body.user_id,
        session_id=body.session_id,
        slash_message=f"/gen_voice {body.prompt}",
        is_memoryless=body.is_memoryless,
    )

    try:
        result = await generate_voice_overview(
            user_prompt=body.prompt,
            session_id=body.session_id,
            redis_client=redis_client,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Voice generation failed for user_id=%s", body.user_id)
        raise HTTPException(status_code=500, detail="Voice generation failed") from exc

    return GenerateVoiceResponse(**result, title=session_title)


@router.get("/generate/assets", response_model=AssetsListResponse)
async def list_assets(
    user_id: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
) -> AssetsListResponse:
    usage = await get_usage_summary(db, user_id)
    if usage is None:
        raise HTTPException(status_code=404, detail="User not found")

    result = await db.execute(
        select(GeneratedAsset)
        .where(GeneratedAsset.user_id == UUID(user_id))
        .order_by(GeneratedAsset.created_at.desc())
    )
    assets = result.scalars().all()

    return AssetsListResponse(
        usage=UsageOut(**usage),
        assets=[
            GeneratedAssetOut(
                id=str(asset.id),
                user_id=str(asset.user_id),
                type=asset.type,
                prompt=asset.prompt,
                url=asset.url,
                created_at=asset.created_at.isoformat(),
            )
            for asset in assets
        ],
    )


@router.delete("/generate/assets/{asset_id}")
async def delete_asset(
    asset_id: str,
    user_id: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_token),
) -> dict:
    """Permanently delete a generated asset for the given user."""

    try:
        asset_uuid = UUID(asset_id)
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid asset or user id")

    result = await db.execute(
        delete(GeneratedAsset).where(
            GeneratedAsset.id == asset_uuid,
            GeneratedAsset.user_id == user_uuid,
        )
    )
    await db.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"deleted": asset_id}
