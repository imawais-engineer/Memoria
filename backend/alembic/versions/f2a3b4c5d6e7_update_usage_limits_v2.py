"""update user usage limits to v2

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-07-18

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE users SET
              max_messages = 20,
              max_videos = 5,
              max_audio = 5
            """
        )
    )
    op.alter_column("users", "max_messages", server_default="20")
    op.alter_column("users", "max_videos", server_default="5")
    op.alter_column("users", "max_audio", server_default="5")


def downgrade() -> None:
    op.alter_column("users", "max_messages", server_default="10")
    op.alter_column("users", "max_videos", server_default="2")
    op.alter_column("users", "max_audio", server_default="2")
    op.execute(
        sa.text(
            """
            UPDATE users SET
              max_messages = 10,
              max_videos = 2,
              max_audio = 2
            """
        )
    )
