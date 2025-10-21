from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime


class APICredentialCreate(BaseModel):
    app_name: str = Field(..., description="Human-friendly name identifying the client application (unique per account)")
    authorized_js_origins: List[str] = Field(..., description="List of allowed JS origins (scheme + host), used for browser-based clients")
    theme: Optional[Dict[str, Any]] = Field(None, description="Optional theme/display options (colors, logo) for this app credential")
    # client_id and client_secret will be generated server-side
    client_secret_ttl_days: Optional[int] = Field(default=0, description="Number of days until the client_secret expires; 0 = never expire")  # 0 means never expire by default


class APICredentialOut(BaseModel):
    id: UUID = Field(..., description="Credential UUID")
    client_id: str = Field(..., description="Public client identifier")
    client_secret_expires_at: Optional[datetime] = Field(None, description="Expiry timestamp for the client_secret, if any")
    authorized_js_origins: Optional[List[str]] = Field(None, description="Allowed JS origins for browser clients")
    created_at: datetime = Field(..., description="UTC timestamp when credential was created")
    app_name: str = Field(..., description="Human-friendly app name for the credential")
    theme: Optional[Dict[str, Any]] = Field(None, description="Theme/display options stored on the app credential")

    model_config = {"from_attributes": True}


class APICredentialCreateResponse(BaseModel):
    id: UUID
    client_id: str
    client_secret: str = Field(..., description="One-time client secret. Store securely; not retrievable later.")
    client_secret_expires_at: Optional[datetime]
    app_name: str

    model_config = {"from_attributes": True}


class APICredentialUpdate(BaseModel):
    app_name: Optional[str] = Field(None, description="New human-friendly app name for this credential")
    authorized_js_origins: Optional[List[str]] = Field(None, description="Updated list of allowed JS origins")
    theme: Optional[Dict[str, Any]] = Field(None, description="Optional theme/display options to store on the app credential")


class APICredentialRotateResponse(BaseModel):
    id: UUID
    client_id: str
    client_secret: str = Field(..., description="New one-time client secret")
    client_secret_expires_at: Optional[datetime]

    model_config = {"from_attributes": True}


class IntegrationCreate(BaseModel):
    name: str = Field(..., description="Integration display name")
    description: Optional[str] = Field(None, description="Short description shown to users")
    schema_id: UUID = Field(..., description="Schema this integration maps to")
    redirect_url: HttpUrl = Field(..., description="Redirect URL used for browser flows, if applicable")
    credential_id: UUID = Field(..., description="App credential UUID this integration will use (must belong to the same account)")
    api_endpoint: str = Field(..., description="Backend API endpoint to submit mapped data to")
    api_headers: Dict[str, str] = Field(default_factory=dict, description="Optional static headers to include when calling the API endpoint")
    method: str = Field(default='POST', description="HTTP method used to call the API endpoint")
    behavior: Dict[str, Any] = Field(..., description="Behavior flags to control mapping/validation (e.g. require_all, allow_partial, auto_submit)")


class IntegrationUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Integration display name")
    description: Optional[str] = Field(None, description="Short description shown to users")
    schema_id: Optional[UUID] = Field(None, description="Schema UUID this integration maps to")
    redirect_url: Optional[HttpUrl] = Field(None, description="Redirect URL used for browser flows, if applicable")
    credential_id: Optional[UUID] = Field(None, description="App credential UUID this integration will use (must belong to the same account)")
    api_endpoint: Optional[str] = Field(None, description="Backend API endpoint to submit mapped data to")
    api_headers: Optional[Dict[str, str]] = Field(None, description="Static headers to include when calling the API endpoint")
    method: Optional[str] = Field(None, description="HTTP method used to call the API endpoint")
    behavior: Optional[Dict[str, Any]] = Field(None, description="Behavior flags to control mapping/validation")
    active: Optional[bool] = Field(None, description="Enable or disable this integration")



class IntegrationOut(BaseModel):
    id: UUID = Field(..., description="Integration UUID")
    name: str = Field(..., description="Integration name")
    credential_id: UUID = Field(..., description="App credential UUID used by this integration")
    schema_id: UUID = Field(..., description="Schema UUID this integration maps to")
    redirect_url: Optional[HttpUrl] = Field(None, description="Optional redirect URL for browser flows")
    api_endpoint: Optional[str] = Field(None, description="Optional backend API endpoint")
    api_headers: Optional[Dict[str, str]] = Field(None, description="Optional static headers for API calls")
    method: Optional[str] = Field(None, description="HTTP method used for API calls")
    behavior: Optional[Dict[str, Any]] = Field(None, description="Behavior flags used by integration")
    created_at: datetime = Field(..., description="Creation timestamp")
    usage: int = Field(0, description="Number of times this integration has been invoked")
    active: bool = Field(..., description="Whether this integration is active")

    model_config = {"from_attributes": True}


class UsageIncrement(BaseModel):
    amount: int = Field(1, description="Amount to increment usage counter by; default 1")

    model_config = {"from_attributes": True}
