"""merge heads abdddf59158b and f6a9b1c2d3e4

Revision ID: m1merge_abdddf_f6a9
Revises: abdddf59158b, f6a9b1c2d3e4
Create Date: 2025-11-12 00:10:00.000000

This is an empty merge revision to unify multiple heads so Alembic can upgrade normally.
"""
from alembic import op
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision = 'm1merge_abdddf_f6a9'
down_revision = ('abdddf59158b', 'f6a9b1c2d3e4')
branch_labels = None
depends_on = None


def upgrade() -> None:
    # merge-only revision; no schema changes
    pass


def downgrade() -> None:
    # no-op for merge revision
    pass
