"""added free trial feature on subscription

Revision ID: 4e8fcccb5f77
Revises: m1merge_abdddf_f6a9
Create Date: 2025-11-12 10:57:09.468931
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = "4e8fcccb5f77"
down_revision: Union[str, Sequence[str], None] = "m1merge_abdddf_f6a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop column only if it exists
    op.execute('ALTER TABLE launch_tokens DROP COLUMN IF EXISTS passthrough')

    # Add new column for free trial
    op.add_column(
        "subscriptions",
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("subscriptions", "trial_ends_at")

    # Recreate passthrough column only if missing
    op.execute(
        "ALTER TABLE launch_tokens ADD COLUMN IF NOT EXISTS passthrough TEXT"
    )
