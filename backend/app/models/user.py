"""SQLAlchemy ORM model for the ``users`` table."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.memory.models import Base


class User(Base):
    """Registered user with a soft password (favorite book)."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    first_name: Mapped[str] = mapped_column(String, nullable=False)
    last_name: Mapped[str] = mapped_column(String, nullable=False)
    favorite_book: Mapped[str] = mapped_column(String, nullable=False)
    global_memory_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    persona: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    image_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    video_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    max_images: Mapped[int] = mapped_column(
        Integer, nullable=False, default=5, server_default=text("5")
    )
    max_videos: Mapped[int] = mapped_column(
        Integer, nullable=False, default=2, server_default=text("2")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<User id={self.id!r} username={self.username!r}>"
