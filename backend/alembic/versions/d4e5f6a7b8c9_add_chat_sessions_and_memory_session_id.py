"""add chat_sessions table and session_id on memories

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-12 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("guest_user_id", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "is_memoryless",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_chat_sessions_guest_user_id"),
        "chat_sessions",
        ["guest_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_chat_sessions_user_id"), "chat_sessions", ["user_id"], unique=False
    )

    op.add_column("memories", sa.Column("session_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_memories_session_id_chat_sessions",
        "memories",
        "chat_sessions",
        ["session_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        op.f("ix_memories_session_id"), "memories", ["session_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_memories_session_id"), table_name="memories")
    op.drop_constraint(
        "fk_memories_session_id_chat_sessions", "memories", type_="foreignkey"
    )
    op.drop_column("memories", "session_id")
    op.drop_index(op.f("ix_chat_sessions_user_id"), table_name="chat_sessions")
    op.drop_index(op.f("ix_chat_sessions_guest_user_id"), table_name="chat_sessions")
    op.drop_table("chat_sessions")
