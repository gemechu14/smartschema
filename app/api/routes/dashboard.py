from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from uuid import UUID

from app.api.deps import get_db
from app.api.deps_auth import require_role_for_account
from app.models.schema_spec import SchemaSpecification
from app.models.integrations import Integration, APICredential
from app.models.auth_models import Role
from pydantic import BaseModel, Field
from typing import List
import datetime

router = APIRouter(prefix="/accounts", tags=["dashboard"])


class DashboardKPIs(BaseModel):
    total_schemas: int = Field(..., description="Count of schemas for the account (not deleted)")
    total_integrations: int = Field(..., description="Count of integrations for the account")
    total_page_requests: int = Field(..., description="Sum of integration.usage for the account (all integrations)")
    total_app_credentials: int = Field(..., description="Count of non-revoked app credentials for the account")
    recent_integrations: List[dict] = Field(default_factory=list, description="Most recent integrations: name, created_at, usage")


@router.get("/{account_id}/dashboard/kpis", response_model=DashboardKPIs, summary="Account dashboard KPIs", description="Return top-level KPI cards for the account.", )
def get_dashboard_kpis(account_id: UUID, tup = Depends(require_role_for_account({Role.OWNER, Role.ADMIN, Role.MEMBER, Role.VIEWER})), db: Session = Depends(get_db)):
    # role check done by dependency
    # Total schemas (not deleted)
    total_schemas = db.query(func.count(SchemaSpecification.id)).filter(SchemaSpecification.account_id == account_id, SchemaSpecification.deleted_at.is_(None)).scalar() or 0

    # Total integrations
    total_integrations = db.query(func.count(Integration.id)).filter(Integration.account_id == account_id).scalar() or 0

    # Total page requests: sum of usage across integrations (active + inactive)
    total_page_requests = db.query(func.coalesce(func.sum(Integration.usage), 0)).filter(Integration.account_id == account_id).scalar() or 0

    # Total app credentials (not revoked)
    total_app_credentials = db.query(func.count(APICredential.id)).filter(APICredential.account_id == account_id, APICredential.revoked == False).scalar() or 0

    recent_rows = db.query(Integration).filter(Integration.account_id == account_id).order_by(Integration.created_at.desc()).limit(3).all()

    return DashboardKPIs(
        total_schemas=int(total_schemas),
        total_integrations=int(total_integrations),
        total_page_requests=int(total_page_requests),
        total_app_credentials=int(total_app_credentials),
        recent_integrations=[{"name": r.name, "created_at": r.created_at, "usage": int(r.usage or 0)} for r in recent_rows],
    )
