from datetime import datetime
from uuid import uuid4
from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base

class EmailVerification(Base):
    __tablename__ = "email_verifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    token_hash = Column(String(128), unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)   # <- tz aware
    consumed_at = Column(DateTime(timezone=True), nullable=True)   # <- tz aware
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)  # optional: keep utc
