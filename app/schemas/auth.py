from typing import Optional, Annotated
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

class Me(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: EmailStr
    first_name: Optional[str]
    last_name: Optional[str]
    is_active: bool

class InviteCreate(BaseModel):
    email: EmailStr
    role: RoleEnum

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


