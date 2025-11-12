"""add trial_ends_at to subscriptions

Revision ID: f6a9b1c2d3e4
Revises: db2657184bfd
Create Date: 2025-11-12 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = 'f6a9b1c2d3e4'
down_revision: Union[str, Sequence[str], None] = 'db2657184bfd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add trial_ends_at to subscriptions."""
    op.add_column('subscriptions', sa.Column('trial_ends_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema: remove trial_ends_at from subscriptions."""
    op.drop_column('subscriptions', 'trial_ends_at')
