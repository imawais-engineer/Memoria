"""Multimodal generation API: image, video, voice, chat models."""

from __future__ import annotations

import logging
from uuid import UUID

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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


class GenerateImageRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    prompt: str = Field(..., min_length=1)


class GenerateVideoRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    prompt: str = Field(..., min_length=1)


class GenerateVoiceRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)
    prompt: str = Field(..., min_length=1)


class GenerateUrlResponse(BaseModel):
    url: str


class GenerateVoiceResponse(BaseModel):
    overview_text: str
    audio_data_uri: str


class GeneratedAssetOut(BaseModel):
    id: str
    user_id: str
    type: str
    prompt: str
    url: str
    created_at: str


class UsageOut(BaseModel):
    image_count: int
    video_count: int
    max_images: int
    max_videos: int
    images_remaining: int
    videos_remaining: int


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


@router.post("/generate/image", response_model=GenerateUrlResponse)
async def create_image(
    body: GenerateImageRequest,
    db: AsyncSession = Depends(get_db),
) -> GenerateUrlResponse:
    allowed = await check_and_increment_usage(db, body.user_id, "image")
    if not allowed:
        raise HTTPException(status_code=429, detail="Image generation limit reached")

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

    return GenerateUrlResponse(url=url)


@router.post("/generate/video", response_model=GenerateUrlResponse)
async def create_video(
    body: GenerateVideoRequest,
    db: AsyncSession = Depends(get_db),
) -> GenerateUrlResponse:
    allowed = await check_and_increment_usage(db, body.user_id, "video")
    if not allowed:
        raise HTTPException(status_code=429, detail="Video generation limit reached")

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

    return GenerateUrlResponse(url=url)


@router.post("/generate/voice", response_model=GenerateVoiceResponse)
async def create_voice(
    body: GenerateVoiceRequest,
    redis_client: redis.Redis = Depends(get_redis),
) -> GenerateVoiceResponse:
    """Two-step voice overview: Qwen summary of session context, then TTS."""

    try:
        result = await generate_voice_overview(
            user_prompt=body.prompt,
            session_id=body.session_id,
            redis_client=redis_client,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Voice generation failed for user_id=%s", body.user_id)
        raise HTTPException(status_code=500, detail="Voice generation failed") from exc

    return GenerateVoiceResponse(**result)


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
