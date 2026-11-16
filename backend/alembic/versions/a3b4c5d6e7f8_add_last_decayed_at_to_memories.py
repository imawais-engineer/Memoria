"""add last_decayed_at to memories

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-07-20 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, Sequence[str], None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "memories",
        sa.Column("last_decayed_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Rows were already decayed under the old compounding formula; stamp them
    # so the first run does not decay from created_at a second time.
    op.execute("UPDATE memories SET last_decayed_at = NOW()")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("memories", "last_decayed_at")
