"""Per-user quotas for chat messages and multimodal generation."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

USAGE_LIMIT_MESSAGE = (
    "You have hit the limit you cannot create more media. This is not a "
    "commercial version. Built for Hackathon and is for test and judges use "
    "only. Great for using / testing memoria."
)


async def check_and_increment_usage(
    db: AsyncSession,
    user_id: str,
    media_type: str,
) -> bool:
    """Return False when the user has reached their limit; otherwise increment."""

    user_uuid = UUID(user_id)
    user = await db.get(User, user_uuid)
    if user is None:
        return False

    if media_type == "image":
        if user.image_count >= user.max_images:
            return False
        user.image_count += 1
    elif media_type == "video":
        if user.video_count >= user.max_videos:
            return False
        user.video_count += 1
    elif media_type == "audio":
        if user.audio_count >= user.max_audio:
            return False
        user.audio_count += 1
    elif media_type == "message":
        if user.message_count >= user.max_messages:
            return False
        user.message_count += 1
    else:
        raise ValueError(f"Unsupported media_type: {media_type!r}")

    await db.commit()
    return True


async def get_usage_summary(db: AsyncSession, user_id: str) -> dict[str, int] | None:
    """Return quota counters for a user."""

    user = await db.get(User, UUID(user_id))
    if user is None:
        return None

    return {
        "message_count": user.message_count,
        "image_count": user.image_count,
        "video_count": user.video_count,
        "audio_count": user.audio_count,
        "max_messages": user.max_messages,
        "max_images": user.max_images,
        "max_videos": user.max_videos,
        "max_audio": user.max_audio,
        "messages_remaining": max(0, user.max_messages - user.message_count),
        "images_remaining": max(0, user.max_images - user.image_count),
        "videos_remaining": max(0, user.max_videos - user.video_count),
        "audio_remaining": max(0, user.max_audio - user.audio_count),
    }
