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
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # Drop passthrough only if it exists
    columns_launch = {c["name"] for c in insp.get_columns("launch_tokens")}
    if "passthrough" in columns_launch:
        op.drop_column("launch_tokens", "passthrough")

    # Add trial_ends_at only if it does NOT exist
    columns_subs = {c["name"] for c in insp.get_columns("subscriptions")}
    if "trial_ends_at" not in columns_subs:
        op.add_column(
            "subscriptions",
            sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    insp = sa.inspect(bind)

    columns_subs = {c["name"] for c in insp.get_columns("subscriptions")}
    if "trial_ends_at" in columns_subs:
        op.drop_column("subscriptions", "trial_ends_at")

    columns_launch = {c["name"] for c in insp.get_columns("launch_tokens")}
    if "passthrough" not in columns_launch:
        op.add_column(
            "launch_tokens",
            sa.Column("passthrough", sa.TEXT(), autoincrement=False, nullable=True),
        )
