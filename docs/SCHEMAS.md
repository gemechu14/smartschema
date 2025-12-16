# Pydantic Schemas Documentation

This document provides detailed documentation for all Pydantic schemas used for request/response validation in the SmartSchema Backend.

## Overview

Pydantic schemas provide:
- Request validation
- Response serialization
- Type safety
- Automatic OpenAPI/Swagger documentation

All schemas inherit from `pydantic.BaseModel` and use Pydantic v2 features.

## Schema Files

### `app/schemas/auth.py`

Authentication and account management schemas.

#### RoleEnum

```python
class RoleEnum(str, Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"
    VIEWER = "VIEWER"
```

**Purpose**: Enum for role values in API requests/responses

**Usage**: Used in membership and invitation schemas

---

#### SignupBody

```python
class SignupBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    first_name: NameStr
    last_name: NameStr
    invite: Optional[str] = None
```

**Purpose**: Request body for user signup

**Fields**:
- `email`: Valid email address (validated by Pydantic)
- `password`: Minimum 6 characters
- `first_name`: 1-80 characters, whitespace stripped
- `last_name`: 1-80 characters, whitespace stripped
- `invite`: Optional invitation token

**Validation**:
- Email format validated
- Password length enforced
- Name fields trimmed and length checked

**Example**:
```json
{
  "email": "user@example.com",
  "password": "securepass123",
  "first_name": "John",
  "last_name": "Doe",
  "invite": null
}
```

---

#### LoginBody

```python
class LoginBody(BaseModel):
    email: EmailStr
    password: str
```

**Purpose**: Request body for login

**Example**:
```json
{
  "email": "user@example.com",
  "password": "securepass123"
}
```

---

#### TokenPair

```python
class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
```

**Purpose**: Response for login/refresh endpoints

**Example**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

---

#### Me

```python
class Me(BaseModel):
    id: UUID
    email: EmailStr
    first_name: Optional[str]
    last_name: Optional[str]
    is_active: bool
    memberships: List[MembershipOut] = []
    is_subscribed: bool = False
```

**Purpose**: Current user profile response

**Fields**:
- `memberships`: List of account memberships
- `is_subscribed`: Whether account has active PRO subscription

**Example**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "is_active": true,
  "memberships": [
    {
      "account_id": "660e8400-e29b-41d4-a716-446655440000",
      "role": "OWNER",
      "account_name": "John's workspace"
    }
  ],
  "is_subscribed": false
}
```

---

#### MembershipOut

```python
class MembershipOut(BaseModel):
    account_id: UUID
    role: RoleEnum
    account_name: Optional[str] = None
```

**Purpose**: Membership information in user profile

---

#### ChangePasswordBody

```python
class ChangePasswordBody(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6)
    confirm_new_password: str = Field(..., min_length=6)
```

**Purpose**: Request body for password change

**Validation**: 
- All fields required
- New password minimum 6 characters
- Frontend should verify `new_password == confirm_new_password`

---

#### ChangeNameBody

```python
class ChangeNameBody(BaseModel):
    first_name: Optional[NameStr] = None
    last_name: Optional[NameStr] = None
```

**Purpose**: Request body for name update

**Note**: At least one field must be provided

---

#### InviteMemberBody

```python
class InviteMemberBody(BaseModel):
    email: EmailStr
    role: RoleEnum = Field(description="One of OWNER/ADMIN/MEMBER/VIEWER")
    manage_schema_ids: Optional[List[UUID]] = Field(
        default=None,
        description="Optional list of schema IDs within this account"
    )
```

**Purpose**: Request body for inviting team members

**Example**:
```json
{
  "email": "newmember@example.com",
  "role": "MEMBER",
  "manage_schema_ids": [
    "770e8400-e29b-41d4-a716-446655440000",
    "880e8400-e29b-41d4-a716-446655440000"
  ]
}
```

---

#### MemberUpdatePermissions

```python
class MemberUpdatePermissions(BaseModel):
    user_id: Optional[UUID] = None
    email: Optional[EmailStr] = None
    role: Optional[RoleEnum] = None
    manage_schema_ids: Optional[List[UUID]] = None
```

**Purpose**: Request body for updating member permissions

**Note**: Either `user_id` or `email` must be provided

---

#### TeamMemberOut

```python
class TeamMemberOut(BaseModel):
    user_id: Optional[UUID] = None
    email: EmailStr
    role: str
    schema_access: List[UUID] = []
    status: str = Field(..., description="One of: active, inactive, pending, expired")
```

**Purpose**: Team member information in list response

---

#### ContactBody

```python
class ContactBody(BaseModel):
    full_name: NameStr
    work_email: EmailStr
    company: Optional[str] = None
    team_size: Optional[str] = None
    use_case: Optional[str] = None
    additional_info: Optional[str] = None
```

**Purpose**: Request body for contact form

---

### `app/schemas/schema_spec.py`

Schema specification schemas.

#### ColumnDef

```python
class ColumnDef(BaseModel):
    name: str
    type: str  # "string" | "integer" | "float" | "boolean" | "date" | "datetime" | "uuid"
```

**Purpose**: Single column definition

**Example**:
```json
{
  "name": "email",
  "type": "string"
}
```

---

#### SchemaJSON

```python
class SchemaJSON(BaseModel):
    columns: List[ColumnDef] = Field(default_factory=list)
```

**Purpose**: Schema structure with columns array

**Example**:
```json
{
  "columns": [
    {"name": "first_name", "type": "string"},
    {"name": "email", "type": "string"},
    {"name": "age", "type": "integer"}
  ]
}
```

---

#### SchemaSpecCreate

```python
class SchemaSpecCreate(BaseModel):
    schema_name: Optional[str] = None
    description: Optional[str] = None
    schema_body: SchemaJSON = Field(alias="schema", validation_alias="schema")
    validators: Dict[str, Dict[str, Any]]
```

**Purpose**: Request body for creating schema

**Field Aliases**:
- API uses `schema` (external)
- Code uses `schema_body` (internal)
- `populate_by_name=True` allows both

**Example**:
```json
{
  "schema_name": "Customer Schema",
  "description": "Customer data",
  "schema": {
    "columns": [
      {"name": "email", "type": "string"},
      {"name": "age", "type": "integer"}
    ]
  },
  "validators": {
    "email": {
      "required": true,
      "unique": true,
      "regex": "^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$"
    },
    "age": {
      "min": 0,
      "max": 150
    }
  }
}
```

---

#### SchemaSpecRead

```python
class SchemaSpecRead(BaseModel):
    id: UUID
    schema_name: str
    description: Optional[str] = None
    schema_body: SchemaJSON = Field(alias="schema")
    validators: Dict[str, Dict[str, Any]]
    columns: Optional[int] = None  # Computed field
    created_at: Optional[str] = None  # Formatted date
    updated_at: Optional[str] = None  # Formatted date
```

**Purpose**: Response schema for schema read operations

**Computed Fields**:
- `columns`: Number of columns (computed from schema)
- `created_at`: Formatted date string (e.g., "Dec 14, 2024")
- `updated_at`: Formatted date string or null

---

#### SchemaSpecUpdate

```python
class SchemaSpecUpdate(BaseModel):
    schema_name: Optional[str] = None
    description: Optional[str] = None
    schema_body: Optional[SchemaJSON] = Field(default=None, alias="schema")
    validators: Optional[Dict[str, Dict[str, Any]]] = None
```

**Purpose**: Request body for updating schema

**Note**: All fields optional, only provided fields are updated

---

### `app/schemas/subscription.py`

Subscription and billing schemas.

#### PlansResponse

```python
class PlansResponse(BaseModel):
    plans: Dict[str, PlanInfo]
```

**Purpose**: Response for plans list endpoint

---

#### PlanInfo

```python
class PlanInfo(BaseModel):
    name: str
    price: int  # Price in cents
    limits: Dict[str, Optional[int]]
```

**Purpose**: Individual plan information

---

#### CheckoutResponse

```python
class CheckoutResponse(BaseModel):
    checkout_session_id: str
    url: str
```

**Purpose**: Response for checkout creation

**Example**:
```json
{
  "checkout_session_id": "cs_test_1234567890",
  "url": "https://checkout.stripe.com/pay/cs_test_..."
}
```

---

#### PortalResponse

```python
class PortalResponse(BaseModel):
    url: str
```

**Purpose**: Response for billing portal creation

---

#### SubscriptionRead

```python
class SubscriptionRead(BaseModel):
    plan: str
    status: str
    current_period_end: Optional[datetime] = None
    display_status: Optional[str] = None
    status_description: Optional[str] = None
    limits: Optional[Dict[str, Optional[int]]] = None
    features: Optional[Dict[str, bool]] = None
```

**Purpose**: Response for subscription status

**Example**:
```json
{
  "plan": "PRO",
  "status": "active",
  "current_period_end": "2025-01-14T00:00:00Z",
  "display_status": "Active",
  "status_description": "Subscription is active and billing is up to date.",
  "limits": {
    "rows": null,
    "schemas": null,
    "members": null
  },
  "features": {
    "api_access": true,
    "white_label_embedding": true,
    "community_support": false,
    "priority_support": true
  }
}
```

---

### `app/schemas/integrations.py`

Integration and credential schemas.

#### APICredentialCreate

```python
class APICredentialCreate(BaseModel):
    app_name: str
    authorized_js_origins: List[str]
    theme: Optional[Dict[str, Any]] = None
    client_secret_ttl_days: Optional[int] = Field(default=0)  # 0 = never expire
```

**Purpose**: Request body for creating API credential

**Example**:
```json
{
  "app_name": "My Web App",
  "authorized_js_origins": ["https://myapp.com", "https://staging.myapp.com"],
  "theme": {
    "primary_color": "#0f172a",
    "logo_url": "https://myapp.com/logo.png"
  },
  "client_secret_ttl_days": 0
}
```

---

#### APICredentialOut

```python
class APICredentialOut(BaseModel):
    id: UUID
    client_id: str
    client_secret_expires_at: Optional[datetime] = None
    authorized_js_origins: Optional[List[str]] = None
    created_at: datetime
    app_name: str
    theme: Optional[Dict[str, Any]] = None
```

**Purpose**: Response for credential read operations

**Note**: Does not include `client_secret` (shown only once on creation)

---

#### APICredentialCreateResponse

```python
class APICredentialCreateResponse(BaseModel):
    id: UUID
    client_id: str
    client_secret: str  # One-time only
    client_secret_expires_at: Optional[datetime]
    app_name: str
```

**Purpose**: Response for credential creation

**Security**: `client_secret` shown only in this response

---

#### APICredentialUpdate

```python
class APICredentialUpdate(BaseModel):
    app_name: Optional[str] = None
    authorized_js_origins: Optional[List[str]] = None
    theme: Optional[Dict[str, Any]] = None
```

**Purpose**: Request body for updating credential

---

#### APICredentialRotateResponse

```python
class APICredentialRotateResponse(BaseModel):
    id: UUID
    client_id: str
    client_secret: str  # New secret, one-time only
    client_secret_expires_at: Optional[datetime]
```

**Purpose**: Response for credential rotation

---

#### IntegrationCreate

```python
class IntegrationCreate(BaseModel):
    name: str
    description: Optional[str] = None
    schema_id: UUID
    redirect_url: HttpUrl
    credential_id: UUID
    api_endpoint: str
    api_headers: Dict[str, str] = Field(default_factory=dict)
    method: str = Field(default='POST')
    behavior: Dict[str, Any]
```

**Purpose**: Request body for creating integration

**Example**:
```json
{
  "name": "Customer Import",
  "description": "Import customer data",
  "schema_id": "990e8400-e29b-41d4-a716-446655440000",
  "credential_id": "aa0e8400-e29b-41d4-a716-446655440000",
  "redirect_url": "https://myapp.com/success",
  "api_endpoint": "https://api.myapp.com/customers",
  "api_headers": {
    "Authorization": "Bearer TOKEN",
    "Content-Type": "application/json"
  },
  "method": "POST",
  "behavior": {
    "require_all": true,
    "allow_partial": false,
    "auto_submit": false
  }
}
```

---

#### IntegrationUpdate

```python
class IntegrationUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    schema_id: Optional[UUID] = None
    redirect_url: Optional[HttpUrl] = None
    credential_id: Optional[UUID] = None
    api_endpoint: Optional[str] = None
    api_headers: Optional[Dict[str, str]] = None
    method: Optional[str] = None
    behavior: Optional[Dict[str, Any]] = None
    active: Optional[bool] = None
```

**Purpose**: Request body for updating integration

---

#### IntegrationOut

```python
class IntegrationOut(BaseModel):
    id: UUID
    name: str
    credential_id: UUID
    schema_id: UUID
    redirect_url: Optional[HttpUrl] = None
    api_endpoint: Optional[str] = None
    api_headers: Optional[Dict[str, str]] = None
    method: Optional[str] = None
    behavior: Optional[Dict[str, Any]] = None
    created_at: datetime
    usage: int = 0
    active: bool
```

**Purpose**: Response for integration read operations

---

#### UsageIncrement

```python
class UsageIncrement(BaseModel):
    amount: int = Field(1, description="Amount to increment usage counter by")
```

**Purpose**: Request body for incrementing integration usage

---

#### IntegrationLaunchRequest

```python
class IntegrationLaunchRequest(BaseModel):
    client_id: str
    client_secret: str
    integration_id: UUID
    overrides: Optional[Dict[str, Any]] = None
```

**Purpose**: Request body for launching integration

**Example**:
```json
{
  "client_id": "abc123...",
  "client_secret": "xyz789...",
  "integration_id": "bb0e8400-e29b-41d4-a716-446655440000",
  "overrides": {
    "user_id": 123,
    "api_header": {
      "Content-Type": "application/json",
      "X-Custom-Header": "value"
    }
  }
}
```

---

#### IntegrationLaunchUrlResponse

```python
class IntegrationLaunchUrlResponse(BaseModel):
    frontend_url: HttpUrl
```

**Purpose**: Response for integration launch

**Example**:
```json
{
  "frontend_url": "https://app.smartschema.io/import-standalone#TOKEN_HERE"
}
```

---

#### IntegrationLaunchInfoResponse

```python
class IntegrationLaunchInfoResponse(BaseModel):
    integration_id: UUID
    schema_spec: Dict[str, Any]  # {"schema": {...}, "validators": {...}}
    app_name: str
    theme: Optional[Dict[str, Any]] = None
    api_endpoint: Optional[str] = None
    api_headers: Optional[Dict[str, str]] = None
    method: Optional[str] = None
    behavior: Optional[Dict[str, Any]] = None
    redirect_url: Optional[HttpUrl] = None
```

**Purpose**: Response for integration launch info endpoint

**Example**:
```json
{
  "integration_id": "bb0e8400-e29b-41d4-a716-446655440000",
  "schema_spec": {
    "schema": {
      "columns": [
        {"name": "email", "type": "string"},
        {"name": "age", "type": "integer"}
      ]
    },
    "validators": {
      "email": {"required": true}
    }
  },
  "app_name": "My Web App",
  "theme": {"primary_color": "#0f172a"},
  "api_endpoint": "https://api.myapp.com/customers",
  "api_headers": {"Authorization": "Bearer TOKEN"},
  "method": "POST",
  "behavior": {"require_all": true},
  "redirect_url": "https://myapp.com/success"
}
```

---

## Common Patterns

### Optional Fields

Use `Optional[Type] = None` for optional fields:
```python
description: Optional[str] = None
```

### Field Validation

Use `Field()` for validation and descriptions:
```python
password: str = Field(min_length=6, description="User password")
```

### Field Aliases

Use aliases for API/Code naming differences:
```python
schema_body: SchemaJSON = Field(alias="schema", validation_alias="schema")
```

### Default Values

Use `default_factory` for mutable defaults:
```python
columns: List[ColumnDef] = Field(default_factory=list)
```

### From Attributes

Use `from_attributes=True` for ORM model serialization:
```python
model_config = ConfigDict(from_attributes=True)
```

## Validation Rules

### Email Validation

- Uses Pydantic's `EmailStr` type
- Validates email format
- Example: `"user@example.com"`

### UUID Validation

- Uses Pydantic's `UUID` type
- Validates UUID format
- Example: `"550e8400-e29b-41d4-a716-446655440000"`

### URL Validation

- Uses Pydantic's `HttpUrl` type
- Validates HTTP/HTTPS URLs
- Example: `"https://example.com"`

### String Constraints

- `NameStr`: 1-80 characters, whitespace stripped
- `min_length`: Minimum string length
- `max_length`: Maximum string length (if specified)

## Best Practices

1. **Use Type Hints**: Always specify types for better validation
2. **Document Fields**: Use `Field(description="...")` for API docs
3. **Validate Early**: Let Pydantic handle validation before business logic
4. **Use Enums**: Use enums for fixed value sets (roles, statuses)
5. **Optional Fields**: Mark nullable fields as `Optional`
6. **Default Values**: Provide sensible defaults where appropriate
7. **Aliases**: Use aliases to match API naming conventions


