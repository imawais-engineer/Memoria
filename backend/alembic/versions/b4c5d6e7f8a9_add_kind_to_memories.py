"""add kind to memories

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-07-21 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b4c5d6e7f8a9"
down_revision: Union[str, Sequence[str], None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "memories",
        sa.Column("kind", sa.String(), nullable=False, server_default="fact"),
    )
    # Backfill from the legacy type. Everything else stays 'fact'.
    op.execute("UPDATE memories SET kind = 'event' WHERE type = 'episodic'")
    op.execute("UPDATE memories SET kind = 'preference' WHERE type = 'preference'")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("memories", "kind")
