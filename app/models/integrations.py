from sqlalchemy import Column, String, ForeignKey, DateTime, Boolean, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base
import datetime
import uuid
from sqlalchemy.dialects.postgresql import UUID as PGUUID


def gen_uuid():
    return str(uuid.uuid4())


class APICredential(Base):
    __tablename__ = 'app_credentials'
    __table_args__ = (
        UniqueConstraint('account_id', 'app_name', name='uq_app_credentials_account_app_name'),
        {'extend_existing': True},
    )

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(PGUUID(as_uuid=True), ForeignKey('accounts.id'), nullable=False)
    # owner/creator user id
    created_by = Column(PGUUID(as_uuid=True), ForeignKey('users.id'), nullable=True)

    client_id = Column(String, nullable=False, unique=True)
    client_secret_hash = Column(String, nullable=False)
    client_secret_expires_at = Column(DateTime, nullable=True)

    # human-friendly app name for this credential (e.g. "My Web App - Staging")
    app_name = Column(String, nullable=False)
    authorized_js_origins = Column(JSONB, nullable=False)
    # optional theme metadata (colors, logo, labels) managed per app credential
    theme = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    revoked = Column(Boolean, default=False)

    # relationship backrefs if needed


class Integration(Base):
    __tablename__ = 'integrations'
    __table_args__ = {'extend_existing': True}

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(PGUUID(as_uuid=True), ForeignKey('accounts.id'), nullable=False)
    created_by = Column(PGUUID(as_uuid=True), ForeignKey('users.id'), nullable=True)

    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    schema_id = Column(PGUUID(as_uuid=True), ForeignKey('schema_specifications.id'), nullable=False)
    redirect_url = Column(String, nullable=True)

    # link integration to a specific app credential (mandatory)
    credential_id = Column(PGUUID(as_uuid=True), ForeignKey('app_credentials.id'), nullable=False)

    api_endpoint = Column(String, nullable=True)
    api_headers = Column(JSONB, nullable=True)
    method = Column(String, nullable=True)

    behavior = Column(JSONB, nullable=True)  # store options like require_all, allow_partial, auto_submit etc.

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    active = Column(Boolean, default=True)
    # usage counter: number of times this integration was invoked
    usage = Column(Integer, default=0)
