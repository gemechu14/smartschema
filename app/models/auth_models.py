from datetime import datetime
from enum import Enum
from uuid import uuid4
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, UniqueConstraint, Enum as SAEnum, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, declarative_base

Base = None
try:
    # if you already have Base defined elsewhere, import it:
    from app.db.base import Base  # adjust if your Base lives here
except Exception:
    # fallback
    from sqlalchemy.orm import declarative_base as _dec
    Base = _dec()

class Role(str, Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"
    VIEWER = "VIEWER"

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    email = Column(String(320), unique=True, index=True, nullable=False)  # store lowercase
    first_name = Column(String(120), nullable=True)
    last_name = Column(String(120), nullable=True)
    password_hash = Column(String(255), nullable=True)
    google_sub = Column(String(128), nullable=True, unique=True)
    is_active = Column(Boolean, default=False, nullable=False)
    email_verified_at = Column(DateTime(timezone=True), nullable=True)  # <- add timezone=True
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)  # optional

    memberships = relationship("Membership", back_populates="user", cascade="all, delete-orphan")

class Account(Base):
    __tablename__ = "accounts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    members = relationship("Membership", back_populates="account", cascade="all, delete-orphan")
    __table_args__ = (UniqueConstraint("owner_user_id", name="uq_account_owner"),)

class Membership(Base):
    __tablename__ = "memberships"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role = Column(SAEnum(Role), nullable=False, default=Role.MEMBER)
    manage_schema_ids = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    account = relationship("Account", back_populates="members")
    user = relationship("User", back_populates="memberships")

    __table_args__ = (UniqueConstraint("account_id", "user_id", name="uq_membership"),)

class Invitation(Base):
    __tablename__ = "invitations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    email = Column(String(320), nullable=False)
    role = Column(SAEnum(Role), nullable=False, default=Role.MEMBER)
    token_hash = Column(String(128), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    accepted_at = Column(DateTime, nullable=True)
    manage_schema_ids = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    jti = Column(String(64), nullable=False, index=True)
    token_hash = Column(String(128), nullable=False, unique=True)
    user_agent = Column(String(255), nullable=True)
    ip = Column(String(64), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)