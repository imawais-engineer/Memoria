"""Per-user quotas for multimodal generation."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


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
        "image_count": user.image_count,
        "video_count": user.video_count,
        "max_images": user.max_images,
        "max_videos": user.max_videos,
        "images_remaining": max(0, user.max_images - user.image_count),
        "videos_remaining": max(0, user.max_videos - user.video_count),
    }
