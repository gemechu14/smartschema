# API Reference

Complete API endpoint documentation for SmartSchema Backend.

## Base URL

- **Development**: `http://localhost:8000`
- **Production**: `https://app.smartschema.io`

## Authentication

Most endpoints require authentication via Bearer token in the Authorization header:

```
Authorization: Bearer <access_token>
```

### Getting Access Token

1. **Signup**: `POST /auth/signup` → Verify email → `POST /auth/login`
2. **Login**: `POST /auth/login` → Returns `access_token` and `refresh_token`
3. **Refresh**: `POST /auth/refresh` → Get new tokens when access token expires

### Token Types

- **Access Token**: Short-lived (15 minutes), used for API requests
- **Refresh Token**: Long-lived (30 days), used to get new access tokens

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message here"
}
```

### HTTP Status Codes

- `200` - Success
- `201` - Created
- `204` - No Content (successful deletion)
- `400` - Bad Request (validation error)
- `401` - Unauthorized (invalid/missing token)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found
- `409` - Conflict (e.g., email already exists)
- `429` - Too Many Requests (rate limited)
- `500` - Internal Server Error

## Endpoints

### Authentication

#### Signup

```http
POST /auth/signup
Content-Type: application/json
```

**Request Body**:
```json
{
  "email": "user@example.com",
  "password": "securepassword123",
  "first_name": "John",
  "last_name": "Doe",
  "invite": null
}
```

**Response** (201):
```json
{
  "ok": true,
  "message": "Verification email sent. Please check your inbox."
}
```

**Notes**:
- If `invite` token provided, joins that account
- Otherwise creates new account with OWNER role
- Sends verification email

---

#### Login

```http
POST /auth/login
Content-Type: application/json
```

**Request Body**:
```json
{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

**Response** (200):
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

---

#### Refresh Token

```http
POST /auth/refresh?refresh_token=<token>
```

**Response** (200):
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

**Notes**: Rotates refresh token (new token invalidates old one)

---

#### Logout

```http
POST /auth/logout?refresh_token=<token>
```

**Response** (200):
```json
{
  "ok": true
}
```

---

#### Verify Email

```http
GET /auth/verify?token=<verification_token>
```

**Response** (200):
```json
{
  "verified": true,
  "message": "Email successfully verified."
}
```

---

#### Resend Verification

```http
POST /auth/verify/resend
Content-Type: application/json
```

**Request Body**:
```json
{
  "email": "user@example.com"
}
```

**Response** (200):
```json
{
  "ok": true,
  "message": "If an account exists, a verification email has been sent."
}
```

**Notes**: Rate-limited with cooldown period

---

#### Get Current User

```http
GET /auth/me
Authorization: Bearer <access_token>
```

**Response** (200):
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "is_active": true,
  "memberships": [
    {
      "account_id": "uuid",
      "role": "OWNER",
      "account_name": "John's workspace"
    }
  ],
  "is_subscribed": false
}
```

---

#### Change Password

```http
POST /auth/change-password
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body**:
```json
{
  "current_password": "oldpassword",
  "new_password": "newpassword123",
  "confirm_new_password": "newpassword123"
}
```

**Response** (200):
```json
{
  "ok": true,
  "message": "Password updated"
}
```

**Notes**: Revokes all refresh tokens

---

#### Change Name

```http
POST /auth/change-name
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body**:
```json
{
  "first_name": "Jane",
  "last_name": "Smith"
}
```

---

#### Password Forgot

```http
POST /auth/password/forgot
Content-Type: application/json
```

**Request Body**:
```json
{
  "email": "user@example.com"
}
```

---

#### Password Reset

```http
POST /auth/password/reset
Content-Type: application/json
```

**Request Body**:
```json
{
  "token": "reset_token_from_email",
  "new_password": "newpassword123"
}
```

---

#### Google OAuth Start

```http
GET /auth/google/start
```

**Response** (200):
```json
{
  "auth_url": "https://accounts.google.com/o/oauth2/v2/auth?..."
}
```

**Notes**: Redirect user to `auth_url`

---

#### Google OAuth Callback

```http
POST /auth/google/callback?code=<authorization_code>
```

**Response** (200):
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

---

### Accounts

#### Get Account

```http
GET /accounts/{account_id}
Authorization: Bearer <access_token>
```

**Permissions**: OWNER, ADMIN

**Response** (200):
```json
{
  "id": "uuid",
  "name": "Account Name"
}
```

---

#### List Team Members

```http
GET /accounts/{account_id}/team_members
Authorization: Bearer <access_token>
```

**Permissions**: OWNER, ADMIN

**Response** (200):
```json
[
  {
    "user_id": "uuid",
    "email": "member@example.com",
    "role": "member",
    "schema_access": ["uuid1", "uuid2"],
    "status": "active"
  }
]
```

---

#### Invite Member

```http
POST /accounts/{account_id}/invite
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Permissions**: OWNER, ADMIN

**Request Body**:
```json
{
  "email": "newmember@example.com",
  "role": "MEMBER",
  "manage_schema_ids": ["uuid1", "uuid2"]
}
```

**Response** (200):
```json
{
  "ok": true,
  "message": "Invitation created (email sent if SMTP available)."
}
```

---

#### Preview Invite

```http
GET /accounts/invites/{token}
```

**Public endpoint** - No authentication required

**Response** (200):
```json
{
  "email": "invited@example.com",
  "role": "MEMBER",
  "account_id": "uuid"
}
```

---

#### Remove Member

```http
DELETE /accounts/{account_id}/members/{user_id}
Authorization: Bearer <access_token>
```

**Permissions**: OWNER

**Response** (200):
```json
{
  "ok": true
}
```

**Notes**: Cannot remove last OWNER

---

#### Delete User

```http
DELETE /accounts/{account_id}/users
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Permissions**: OWNER, ADMIN

**Request Body**:
```json
{
  "email": "user@example.com"
}
```

**Response** (200):
```json
{
  "ok": true
}
```

**Notes**: Cannot delete account owner

---

#### Rename Account

```http
PATCH /accounts/{account_id}
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Permissions**: OWNER

**Request Body**:
```json
{
  "name": "New Account Name"
}
```

---

#### Update Member Permissions

```http
PUT /accounts/{account_id}/members/permissions
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Permissions**: OWNER, ADMIN

**Request Body**:
```json
{
  "user_id": "uuid",
  "role": "MEMBER",
  "manage_schema_ids": ["uuid1", "uuid2"]
}
```

**Notes**: Can use `email` instead of `user_id`

---

### Schemas

#### Create Schema

```http
POST /accounts/{account_id}/schemas
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Permissions**: OWNER, ADMIN

**Request Body**:
```json
{
  "schema_name": "Customer Schema",
  "description": "Customer data schema",
  "schema": {
    "columns": [
      {"name": "first_name", "type": "string"},
      {"name": "email", "type": "string"},
      {"name": "age", "type": "integer"}
    ]
  },
  "validators": {
    "email": {"required": true, "format": "email"},
    "age": {"min": 0, "max": 150}
  }
}
```

**Response** (200):
```json
{
  "id": "uuid",
  "schema_name": "Customer Schema",
  "description": "Customer data schema",
  "schema": {...},
  "validators": {...},
  "columns": 3,
  "created_at": "Dec 14, 2024",
  "updated_at": null
}
```

---

#### List Schemas

```http
GET /accounts/{account_id}/schemas
Authorization: Bearer <access_token>
```

**Permissions**: All roles (visibility-aware)

**Response** (200):
```json
[
  {
    "id": "uuid",
    "schema_name": "Customer Schema",
    "schema": {...},
    "validators": {...},
    "columns": 3,
    "created_at": "Dec 14, 2024"
  }
]
```

**Notes**: 
- OWNER/ADMIN see all schemas
- MEMBER/VIEWER see only schemas in their `manage_schema_ids`

---

#### Get Schema

```http
GET /accounts/{account_id}/schemas/{schema_id}
Authorization: Bearer <access_token>
```

**Permissions**: All roles (visibility-aware)

**Response**: Same as Create Schema

---

#### Update Schema

```http
PUT /accounts/{account_id}/schemas/{schema_id}
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Permissions**: OWNER, ADMIN

**Request Body**: Same structure as Create (all fields optional)

---

#### Delete Schema

```http
DELETE /accounts/{account_id}/schemas/{schema_id}
Authorization: Bearer <access_token>
```

**Permissions**: OWNER, ADMIN

**Response**: 204 No Content

**Notes**: Soft delete, removes from member permissions

---

### Subscriptions

#### Get Subscription

```http
GET /accounts/{account_id}/subscriptions/
Authorization: Bearer <access_token>
```

**Permissions**: OWNER

**Response** (200):
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

#### Create Checkout

```http
POST /accounts/{account_id}/subscriptions/checkout
Authorization: Bearer <access_token>
```

**Permissions**: OWNER

**Response** (200):
```json
{
  "checkout_session_id": "cs_test_...",
  "url": "https://checkout.stripe.com/..."
}
```

**Notes**: Redirect user to `url` to complete payment

---

#### Create Portal

```http
POST /accounts/{account_id}/subscriptions/portal
Authorization: Bearer <access_token>
```

**Permissions**: OWNER

**Response** (200):
```json
{
  "url": "https://billing.stripe.com/..."
}
```

---

### Integrations

#### Create Credential

```http
POST /accounts/{account_id}/credentials
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Permissions**: OWNER, ADMIN

**Request Body**:
```json
{
  "app_name": "My Web App",
  "authorized_js_origins": ["https://myapp.com"],
  "theme": {"primary_color": "#0f172a"},
  "client_secret_ttl_days": 0
}
```

**Response** (200):
```json
{
  "id": "uuid",
  "client_id": "abc123...",
  "client_secret": "xyz789...",
  "client_secret_expires_at": null,
  "app_name": "My Web App"
}
```

**Notes**: `client_secret` shown only once

---

#### List Credentials

```http
GET /accounts/{account_id}/credentials
Authorization: Bearer <access_token>
```

**Permissions**: All roles

**Response** (200):
```json
[
  {
    "id": "uuid",
    "client_id": "abc123...",
    "app_name": "My Web App",
    "authorized_js_origins": ["https://myapp.com"],
    "created_at": "2024-12-14T00:00:00Z"
  }
]
```

---

#### Update Credential

```http
PATCH /accounts/{account_id}/credentials/{credential_id}
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Permissions**: OWNER, ADMIN

**Request Body**:
```json
{
  "app_name": "Updated Name",
  "authorized_js_origins": ["https://myapp.com", "https://staging.myapp.com"]
}
```

---

#### Rotate Credential

```http
POST /accounts/{account_id}/credentials/{credential_id}/rotate
Authorization: Bearer <access_token>
```

**Permissions**: OWNER, ADMIN

**Response** (200):
```json
{
  "id": "uuid",
  "client_id": "abc123...",
  "client_secret": "new_secret...",
  "client_secret_expires_at": null
}
```

---

#### Delete Credential

```http
DELETE /accounts/{account_id}/credentials/{credential_id}
Authorization: Bearer <access_token>
```

**Permissions**: OWNER, ADMIN, MEMBER

**Response**: 204 No Content

---

#### Create Integration

```http
POST /accounts/{account_id}/integrations
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Permissions**: All roles (MEMBER restricted to their schemas)

**Request Body**:
```json
{
  "name": "Customer Import",
  "description": "Import customer data",
  "schema_id": "uuid",
  "credential_id": "uuid",
  "redirect_url": "https://myapp.com/success",
  "api_endpoint": "https://api.myapp.com/customers",
  "api_headers": {"Authorization": "Bearer TOKEN"},
  "method": "POST",
  "behavior": {"require_all": true, "auto_submit": false}
}
```

---

#### List Integrations

```http
GET /accounts/{account_id}/integrations
Authorization: Bearer <access_token>
```

**Permissions**: All roles (visibility-aware)

**Response** (200):
```json
[
  {
    "id": "uuid",
    "name": "Customer Import",
    "credential_id": "uuid",
    "schema_id": "uuid",
    "api_endpoint": "https://api.myapp.com/customers",
    "method": "POST",
    "usage": 42,
    "active": true
  }
]
```

---

#### Update Integration

```http
PATCH /accounts/{account_id}/integrations/{integration_id}
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Permissions**: OWNER, ADMIN

**Request Body**: Same as Create (all fields optional)

---

#### Increment Usage

```http
POST /accounts/{account_id}/integrations/{integration_id}/usage
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body**:
```json
{
  "amount": 1
}
```

---

#### Launch Integration

```http
POST /accounts/integrations/launch
Content-Type: application/json
```

**Public endpoint** - Authenticates via client_id/client_secret

**Request Body**:
```json
{
  "client_id": "abc123...",
  "client_secret": "xyz789...",
  "integration_id": "uuid",
  "overrides": {
    "user_id": 123,
    "api_header": {"Content-Type": "application/json"}
  }
}
```

**Response** (200):
```json
{
  "frontend_url": "https://app.smartschema.io/import-standalone#TOKEN"
}
```

---

#### Get Launch Info

```http
GET /accounts/integrations/launch/info
Authorization: Bearer <launch_token>
```

**Response** (200):
```json
{
  "integration_id": "uuid",
  "schema_spec": {
    "schema": {...},
    "validators": {...}
  },
  "app_name": "My Web App",
  "api_endpoint": "https://api.myapp.com/customers",
  "method": "POST"
}
```

---

### Dashboard

#### Get KPIs

```http
GET /accounts/{account_id}/dashboard/kpis
Authorization: Bearer <access_token>
```

**Permissions**: All roles

**Response** (200):
```json
{
  "total_schemas": 5,
  "total_integrations": 3,
  "total_page_requests": 150,
  "total_app_credentials": 2,
  "recent_integrations": [
    {
      "name": "Customer Import",
      "created_at": "2024-12-14T00:00:00Z",
      "usage": 42
    }
  ]
}
```

---

### Public Endpoints

#### List Plans

```http
GET /plans
```

**Public endpoint** - No authentication required

**Response** (200):
```json
{
  "FREE": {
    "id": "free",
    "name": "Free",
    "price": 0,
    "limits": {"rows": 1000, "schemas": 5, "members": 3},
    "features": {...}
  },
  "PRO": {
    "id": "pro",
    "name": "Pro",
    "price": 39900,
    "limits": {"rows": null, "schemas": null, "members": null},
    "features": {...}
  }
}
```

---

#### Contact Form

```http
POST /contact
Content-Type: application/json
```

**Public endpoint** - No authentication required

**Request Body**:
```json
{
  "full_name": "John Doe",
  "work_email": "john@example.com",
  "company": "Acme Corp",
  "team_size": "10-50",
  "use_case": "Data import automation",
  "additional_info": "Looking for enterprise solution"
}
```

---

#### Loci AI Mapper

```http
POST /loci-ai-mapper
Content-Type: application/json
```

**Public endpoint** - No authentication required

**Request Body**:
```json
{
  "schema_columns": ["first_name", "last_name", "email"],
  "import_columns": ["fname", "lname", "email_address"],
  "min_confidence": 0.50,
  "model_name": "sentence-transformers/all-MiniLM-L6-v2"
}
```

**Response** (200):
```json
{
  "matches": [
    {
      "schema": "first_name",
      "import": "fname",
      "confidence": 0.95
    }
  ],
  "unmatched_schema": ["last_name"],
  "unmatched_import": ["email_address"]
}
```

---

### Stripe Webhook

```http
POST /stripe/webhook
stripe-signature: <signature>
Content-Type: application/json
```

**Webhook endpoint** - Validates Stripe signature

**Request Body**: Stripe event JSON

**Response** (200):
```json
{
  "received": true
}
```

**Notes**: Idempotent processing via event ID tracking

---

## Rate Limiting

Currently not implemented. Recommended:
- Email verification resend: 60 seconds cooldown
- Login attempts: 5 per minute per IP
- API requests: 100 per minute per token

## Pagination

Currently not implemented. All list endpoints return all results.

Recommended pagination parameters:
- `page`: Page number (default: 1)
- `per_page`: Items per page (default: 20, max: 100)

## Filtering & Sorting

Currently not implemented. Recommended:
- `sort`: Field to sort by (default: created_at)
- `order`: asc or desc (default: desc)
- `filter`: Field filters (e.g., `?status=active`)


