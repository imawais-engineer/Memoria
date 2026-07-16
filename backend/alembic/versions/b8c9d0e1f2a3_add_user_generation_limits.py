"""add user generation usage limits

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-07-16 13:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("image_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "users",
        sa.Column("video_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "users",
        sa.Column("max_images", sa.Integer(), server_default=sa.text("5"), nullable=False),
    )
    op.add_column(
        "users",
        sa.Column("max_videos", sa.Integer(), server_default=sa.text("2"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "max_videos")
    op.drop_column("users", "max_images")
    op.drop_column("users", "video_count")
    op.drop_column("users", "image_count")
