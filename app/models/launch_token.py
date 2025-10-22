from datetime import datetime
import uuid
from sqlalchemy import Column, DateTime, Boolean, String
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class LaunchToken(Base):
    __tablename__ = 'launch_tokens'
    __table_args__ = {'extend_existing': True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # store a hash of the token for lookup
    token_hash = Column(String, nullable=False, unique=True)
    integration_id = Column(UUID(as_uuid=True), nullable=False)
    credential_id = Column(UUID(as_uuid=True), nullable=False)
    account_id = Column(UUID(as_uuid=True), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
