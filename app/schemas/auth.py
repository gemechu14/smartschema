from typing import Optional, Annotated, List
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict, StringConstraints
from uuid import UUID
from enum import Enum

class RoleEnum(str, Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"
    VIEWER = "VIEWER"

NameStr = Annotated[str, StringConstraints(min_length=1, max_length=80, strip_whitespace=True)]

class SignupBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    first_name: NameStr
    last_name: NameStr
    invite: Optional[str] = None

class LoginBody(BaseModel):
    email: EmailStr
    password: str

class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class MembershipOut(BaseModel):
    account_id: UUID
    role: RoleEnum
    account_name: Optional[str] = None  
class Me(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: EmailStr
    first_name: Optional[str]
    last_name: Optional[str]
    is_active: bool
    memberships: List[MembershipOut] = []
    # Whether the current account is actively subscribed to PRO
    is_subscribed: bool = False

class MemberOut(BaseModel):
    user_id: UUID
    email: EmailStr
    role: RoleEnum
    first_name: Optional[str]
    last_name: Optional[str]

class GoogleStartOut(BaseModel):
    auth_url: str

class AccountRename(BaseModel):
    name: str

# --- responses & extra request models for verification flow ---

class SignupResponse(BaseModel):
    ok: bool = True
    message: str = "Verification email sent. Please check your inbox."

class VerifyResponse(BaseModel):
    verified: bool
    message: str

class ResendBody(BaseModel):
    email: EmailStr = Field(..., description="User's email (username).")

class MessageResponse(BaseModel):
    ok: bool = True
    message: str

class PasswordForgotBody(BaseModel):
    email: EmailStr = Field(..., description="Account email (username).")

class PasswordResetBody(BaseModel):
    token: str = Field(..., description="Raw reset token from email link.")
    new_password: str = Field(..., min_length=6, description="New password (min 6 chars).")


class ChangePasswordBody(BaseModel):
    current_password: str = Field(..., min_length=1, description="Current password")
    new_password: str = Field(..., min_length=6, description="New password (min 6 chars)")
    confirm_new_password: str = Field(..., min_length=6, description="Confirm new password")
    # names removed from this model; use ChangeNameBody to update profile names separately

class ChangeNameBody(BaseModel):
    first_name: Optional[NameStr] = None
    last_name: Optional[NameStr] = None

class InviteMemberBody(BaseModel):
    email: EmailStr
    role: RoleEnum = Field(description="One of OWNER/ADMIN/MEMBER/VIEWER. Only OWNER can invite.")
    manage_schema_ids: Optional[List[UUID]] = Field(
        default=None,
        description="Optional list of schema IDs within this account the member may manage (admins/owners ignore)."
    )

class MemberUpdatePermissions(BaseModel):
    user_id: Optional[UUID] = Field(
        default=None,
        description="Optional user id. If omitted the path param will be used."
    )
    email: Optional[EmailStr] = Field(
        default=None,
        description="Optional email. If provided and user_id is omitted, update invites for this email only."
    )
    role: Optional[RoleEnum] = Field(
        default=None,
        description="Optional role to assign (OWNER/ADMIN/MEMBER/VIEWER). Promoting to OWNER via this API is not allowed."
    )
    manage_schema_ids: Optional[List[UUID]] = Field(
        default=None,
        description="Replace allowed schemas list for this member. Set [] to clear."
    )

class TeamMemberOut(BaseModel):
    user_id: Optional[UUID] = None
    email: EmailStr
    role: str
    schema_access: List[UUID] = []
    status: str = Field(..., description="One of: active, inactive, pending, expired")

class SchemaCreate(BaseModel):
    schema_name: str
    schema_body: dict = Field(alias="schema", validation_alias="schema")
    validators: Optional[dict] = None

    model_config = ConfigDict(populate_by_name=True)

class SchemaOut(BaseModel):
    id: UUID
    schema_name: str
    schema_body: dict = Field(alias="schema", validation_alias="schema")
    validators: Optional[dict] = None
    account_id: UUID
    created_by_user_id: Optional[UUID]

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ContactBody(BaseModel):
    full_name: NameStr = Field(..., description="Full name of the sender")
    work_email: EmailStr = Field(..., description="Work email address to reply to")
    company: Optional[str] = Field(None, description="Company name")
    team_size: Optional[str] = Field(None, description="Team size or 'Select size' value")
    use_case: Optional[str] = Field(None, description="Short description of intended use case")
    additional_info: Optional[str] = Field(None, description="Longer free-text message or requirements")


