"""add consolidation fields to memories

Revision ID: a1b2c3d4e5f6
Revises: f9ff25fe222b
Create Date: 2026-07-11 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f9ff25fe222b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "memories",
        sa.Column(
            "is_consolidated",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "memories",
        sa.Column("consolidated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_user_consolidated", "memories", ["user_id", "is_consolidated"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_user_consolidated", table_name="memories")
    op.drop_column("memories", "consolidated_at")
    op.drop_column("memories", "is_consolidated")
