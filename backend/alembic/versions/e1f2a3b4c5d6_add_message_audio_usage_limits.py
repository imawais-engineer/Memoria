"""add message and audio usage limits

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-07-18

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "message_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "audio_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "max_messages",
            sa.Integer(),
            nullable=False,
            server_default="10",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "max_audio",
            sa.Integer(),
            nullable=False,
            server_default="2",
        ),
    )

    op.execute(
        sa.text(
            """
            UPDATE users SET
              message_count = 0,
              image_count = 0,
              video_count = 0,
              audio_count = 0,
              max_messages = 10,
              max_images = 5,
              max_videos = 2,
              max_audio = 2
            """
        )
    )


def downgrade() -> None:
    op.drop_column("users", "max_audio")
    op.drop_column("users", "max_messages")
    op.drop_column("users", "audio_count")
    op.drop_column("users", "message_count")
