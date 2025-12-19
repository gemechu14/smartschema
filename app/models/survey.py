from datetime import datetime
from enum import Enum
from uuid import uuid4
from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint, Enum as SAEnum, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db.base import Base


class SurveyStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class Survey(Base):
    __tablename__ = "surveys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    schema_id = Column(UUID(as_uuid=True), ForeignKey("schema_specifications.id", ondelete="SET NULL"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(SAEnum(SurveyStatus), nullable=False, default=SurveyStatus.ACTIVE)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=datetime.utcnow, nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)


class SurveyInvite(Base):
    __tablename__ = "survey_invites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    survey_id = Column(UUID(as_uuid=True), ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(320), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    opened_at = Column(DateTime(timezone=True), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("survey_id", "email", name="uq_survey_invite_email"),
        Index("ix_survey_invites_token_hash", "token_hash"),
        Index("ix_survey_invites_email", "email"),
        Index("ix_survey_invites_survey_id", "survey_id"),
    )


class SurveyResponse(Base):
    __tablename__ = "survey_responses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    survey_id = Column(UUID(as_uuid=True), ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False, index=True)
    invite_id = Column(UUID(as_uuid=True), ForeignKey("survey_invites.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    schema_id = Column(UUID(as_uuid=True), ForeignKey("schema_specifications.id", ondelete="SET NULL"), nullable=True)
    response_data = Column(JSONB, nullable=False)
    submitted_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_survey_responses_survey_id", "survey_id"),
        Index("ix_survey_responses_invite_id", "invite_id"),
    )













