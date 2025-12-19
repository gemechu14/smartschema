"""add survey tables

Revision ID: 001_add_survey_tables
Revises: f9218dd57616
Create Date: 2025-12-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_add_survey_tables'
down_revision: Union[str, Sequence[str], None] = 'f9218dd57616'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - create survey tables."""
    
    # Create surveys table
    op.create_table(
        'surveys',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('schema_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('ACTIVE', 'CLOSED', name='surveystatus'), nullable=False, server_default='ACTIVE'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['schema_id'], ['schema_specifications.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_surveys_account_id', 'surveys', ['account_id'])
    op.create_index('ix_surveys_schema_id', 'surveys', ['schema_id'])
    op.create_index('ix_surveys_created_by_user_id', 'surveys', ['created_by_user_id'])
    
    # Create survey_invites table
    op.create_table(
        'survey_invites',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('survey_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(length=320), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('opened_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['survey_id'], ['surveys.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash', name='uq_survey_invites_token_hash'),
        sa.UniqueConstraint('survey_id', 'email', name='uq_survey_invite_email')
    )
    op.create_index('ix_survey_invites_survey_id', 'survey_invites', ['survey_id'])
    op.create_index('ix_survey_invites_email', 'survey_invites', ['email'])
    op.create_index('ix_survey_invites_token_hash', 'survey_invites', ['token_hash'])
    
    # Create survey_responses table
    op.create_table(
        'survey_responses',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('survey_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('invite_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('schema_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('response_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['survey_id'], ['surveys.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invite_id'], ['survey_invites.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['schema_id'], ['schema_specifications.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('invite_id', name='uq_survey_responses_invite_id')
    )
    op.create_index('ix_survey_responses_survey_id', 'survey_responses', ['survey_id'])
    op.create_index('ix_survey_responses_invite_id', 'survey_responses', ['invite_id'])


def downgrade() -> None:
    """Downgrade schema - drop survey tables."""
    
    # Drop tables in reverse order
    op.drop_index('ix_survey_responses_invite_id', 'survey_responses')
    op.drop_index('ix_survey_responses_survey_id', 'survey_responses')
    op.drop_table('survey_responses')
    
    op.drop_index('ix_survey_invites_token_hash', 'survey_invites')
    op.drop_index('ix_survey_invites_email', 'survey_invites')
    op.drop_index('ix_survey_invites_survey_id', 'survey_invites')
    op.drop_table('survey_invites')
    
    op.drop_index('ix_surveys_created_by_user_id', 'surveys')
    op.drop_index('ix_surveys_schema_id', 'surveys')
    op.drop_index('ix_surveys_account_id', 'surveys')
    op.drop_table('surveys')
    
    # Drop enum type
    op.execute('DROP TYPE surveystatus')















