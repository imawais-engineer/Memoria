"""add users table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-12 14:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  op.create_table(
      "users",
      sa.Column("id", sa.UUID(), nullable=False),
      sa.Column("username", sa.String(), nullable=False),
      sa.Column("first_name", sa.String(), nullable=False),
      sa.Column("last_name", sa.String(), nullable=False),
      sa.Column("favorite_book", sa.String(), nullable=False),
      sa.Column(
          "created_at",
          sa.DateTime(timezone=True),
          server_default=sa.text("now()"),
          nullable=False,
      ),
      sa.PrimaryKeyConstraint("id"),
  )
  op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)


def downgrade() -> None:
  op.drop_index(op.f("ix_users_username"), table_name="users")
  op.drop_table("users")
