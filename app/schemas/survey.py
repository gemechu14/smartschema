from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from uuid import UUID
from enum import Enum


class SurveyStatusEnum(str, Enum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


# ============ Survey Management Schemas ============

class SurveyCreateBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Survey name")
    description: Optional[str] = Field(None, description="Survey description")
    schema_id: Optional[UUID] = Field(None, description="Reference to existing schema specification")
    emails: Optional[List[EmailStr]] = Field(None, description="List of email addresses to invite (optional)")
    expires_at: Optional[datetime] = Field(None, description="Survey expiration date (optional)")


class SurveyUpdateBody(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Survey name")
    description: Optional[str] = Field(None, description="Survey description")
    emails: Optional[List[EmailStr]] = Field(None, description="Additional emails to invite (only new ones will be sent)")
    status: Optional[SurveyStatusEnum] = Field(None, description="Survey status")


class SurveyInviteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    email: str
    sent_at: Optional[datetime]
    opened_at: Optional[datetime]
    submitted_at: Optional[datetime]
    expires_at: datetime
    revoked_at: Optional[datetime]
    
    @property
    def is_expired(self) -> bool:
        from app.core.security import now_utc
        return now_utc() > self.expires_at if self.expires_at else False
    
    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None
    
    @property
    def is_submitted(self) -> bool:
        return self.submitted_at is not None


class SurveyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    account_id: UUID
    schema_id: Optional[UUID]
    schema_name: Optional[str] = Field(None, description="Name of the associated schema")
    name: str
    description: Optional[str]
    status: SurveyStatusEnum
    expires_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]
    created_by_user_id: Optional[UUID]
    
    # Computed stats (to be added by route handler)
    total_invites: int = 0
    opened_count: int = 0
    submitted_count: int = 0


class SurveyDetailOut(SurveyOut):
    invites: List[SurveyInviteOut] = []


class SurveyCreateResponse(BaseModel):
    ok: bool = True
    message: str = "Survey created successfully"
    survey: SurveyOut
    invites_sent: int


class SurveyListResponse(BaseModel):
    surveys: List[SurveyOut]
    total: int


# ============ Public Submission Schemas ============

class SurveyOpenResponse(BaseModel):
    survey_id: UUID
    survey_name: str
    survey_description: Optional[str]
    schema: Optional[dict] = Field(None, description="Schema definition if available")
    already_submitted: bool = False
    expires_at: Optional[datetime]


class SurveyOpenBody(BaseModel):
    token: str = Field(..., description="Survey invitation token (extracted from URL fragment)")


class SurveySubmitBody(BaseModel):
    token: str = Field(..., description="Survey invitation token")
    response_data: dict = Field(..., description="Survey response data (must match schema if present)")


class SurveyStatusBody(BaseModel):
    token: str = Field(..., description="Survey invitation token (extracted from URL fragment)")


class SurveySubmitResponse(BaseModel):
    ok: bool = True
    message: str = "Survey submitted successfully"
    response_id: UUID


# ============ Admin Actions ============

class SurveyCloseResponse(BaseModel):
    ok: bool = True
    message: str = "Survey closed successfully"


class SurveyRevokeInviteBody(BaseModel):
    invite_id: UUID = Field(..., description="Invite ID to revoke")


class MessageResponse(BaseModel):
    ok: bool = True
    message: str


# ============ Survey Overview/Statistics ============

class SurveyOverviewOut(BaseModel):
    total_surveys: int = Field(..., description="Total number of surveys (excluding deleted)")
    active_surveys: int = Field(..., description="Number of active surveys")
    closed_surveys: int = Field(..., description="Number of closed surveys")
    total_responses: int = Field(..., description="Total number of survey responses")


class SurveyOverviewResponse(BaseModel):
    overviews: SurveyOverviewOut


# ============ Survey Statistics ============

class SurveyStatsOut(BaseModel):
    total_invites: int = Field(..., description="Total number of invitations sent")
    opened: int = Field(..., description="Number of invitations opened")
    submitted: int = Field(..., description="Number of responses submitted")
    response_rate: float = Field(..., description="Response rate percentage (submitted/total_invites * 100)")
    expired_invites: int = Field(..., description="Number of expired invitations")
    revoked_invites: int = Field(..., description="Number of revoked invitations")


class SurveyStatsResponse(BaseModel):
    survey_id: UUID
    name: str
    status: str = Field(..., description="Survey status (active/closed)")
    expires_at: Optional[datetime]
    stats: SurveyStatsOut
    invites: List[SurveyInviteOut] = Field(default_factory=list, description="List of all invited members")


# ============ Survey Response Schemas ============

def transform_response_data_to_rows(response_data: dict) -> dict:
    """
    Transform columnar response data to row-based format.
    
    Input format:
    {
        "columns": [
            {"name": "email", "type": "string", "values": ["a@b.com", "c@d.com"]},
            {"name": "Name", "type": "string", "values": ["Alice", "Bob"]}
        ]
    }
    
    Output format:
    {
        "rows": [
            {"email": "a@b.com", "Name": "Alice"},
            {"email": "c@d.com", "Name": "Bob"}
        ]
    }
    """
    if not isinstance(response_data, dict):
        return {"rows": []}
    
    # Check if it's already in row format
    if "rows" in response_data:
        return response_data
    
    # Transform from columnar to row format
    if "columns" in response_data and isinstance(response_data["columns"], list):
        columns = response_data["columns"]
        if not columns:
            return {"rows": []}
        
        # Get the number of rows (length of first column's values)
        num_rows = len(columns[0].get("values", [])) if columns else 0
        
        # Build rows
        rows = []
        for i in range(num_rows):
            row = {}
            for col in columns:
                col_name = col.get("name", "")
                col_values = col.get("values", [])
                if i < len(col_values):
                    row[col_name] = col_values[i]
                else:
                    row[col_name] = None
            rows.append(row)
        
        return {"rows": rows}
    
    # If format is unknown, return as-is but wrap in rows
    return {"rows": [response_data]}


class SurveyResponseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    survey_id: UUID
    invite_id: UUID
    schema_id: Optional[UUID]
    schema_name: Optional[str] = Field(None, description="Name of the schema specification")
    email: Optional[str] = Field(None, description="Email of the respondent (from invite)")
    sent_at: Optional[datetime] = Field(None, description="When the invitation was sent")
    response_data: dict = Field(..., description="Survey response data (in row format)")
    submitted_at: datetime


class SurveyResponseListResponse(BaseModel):
    responses: List[SurveyResponseOut]
    total: int


class SurveyResponseDetailResponse(BaseModel):
    response: SurveyResponseOut








