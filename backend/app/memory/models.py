"""SQLAlchemy ORM model for the ``memories`` table.

Module 2 defines only the schema/model. Alembic migrations and pgvector index
creation live elsewhere (not in this file).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Dimensionality of the embedding vectors (DashScope text-embedding-v3 -> 1024).
EMBEDDING_DIM = 1024


class Base(AsyncAttrs, DeclarativeBase):
    """Async-enabled declarative base for all ORM models."""


class Memory(Base):
    """A single stored memory belonging to a user.

    ``type`` is expected to be one of ``'core'``, ``'episodic'``,
    ``'semantic'`` or ``'procedural'``.
    """

    __tablename__ = "memories"

    # Table-level indexes for common consolidation and type lookups.
    __table_args__ = (
        Index("ix_memories_user_id_type", "user_id", "type"),
        Index("ix_user_consolidated", "user_id", "is_consolidated"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    type: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(
        Vector(EMBEDDING_DIM), nullable=False
    )
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_accessed: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    decay_rate: Mapped[float] = mapped_column(Float, default=0.01)
    parent_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("memories.id"), nullable=True
    )
    is_consolidated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    consolidated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # ``metadata`` is reserved by SQLAlchemy's Declarative API (``Base.metadata``),
    # so the Python attribute is ``meta_data`` while the DB column stays
    # ``metadata``. ``default=dict`` avoids sharing one mutable dict across rows.
    meta_data: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    # Soft-delete flag used by the forgetting/consolidation engine.
    archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    superseded: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    superseded_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("memories.id"), nullable=True
    )
    session_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<Memory id={self.id!r} user_id={self.user_id!r} "
            f"type={self.type!r} importance={self.importance!r}>"
        )
