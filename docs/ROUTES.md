# API Routes Documentation

This document provides detailed documentation for all API route handlers in the SmartSchema Backend.

## Overview

Routes are organized by functionality in `app/api/routes/`. Each route file defines an `APIRouter` with a prefix and tags for OpenAPI documentation.

## Route Files

### `app/api/routes/auth.py`

**Prefix**: `/auth`  
**Tag**: `auth`

Authentication and user management endpoints.

#### POST /auth/signup

**Summary**: Create user and send verification email

**Description**: 
- Creates a new user with unique email
- If `invite` token provided, joins that account with specified role
- Otherwise creates new account with OWNER role
- Sends verification email
- Login blocked until email verified

**Request Body**: `SignupBody`
```json
{
  "email": "user@example.com",
  "password": "securepass123",
  "first_name": "John",
  "last_name": "Doe",
  "invite": null
}
```

**Response**: `SignupResponse` (201)
```json
{
  "ok": true,
  "message": "Verification email sent. Please check your inbox."
}
```

**Errors**:
- `409`: Email already registered
- `500`: Failed to send verification email

**Implementation Notes**:
- Email normalized to lowercase
- Names parsed from email if missing
- Race condition handling for account creation
- Invite permissions applied to membership

---

#### GET /auth/verify

**Summary**: Verify email using token

**Query Parameters**:
- `token` (required): Verification token from email

**Response**: `VerifyResponse` (200)
```json
{
  "verified": true,
  "message": "Email successfully verified."
}
```

**Errors**:
- `400`: Invalid or expired token

**Implementation Notes**:
- Token validated via hash lookup
- Token marked as consumed
- User activated (`is_active=True`, `email_verified_at` set)

---

#### POST /auth/verify/resend

**Summary**: Resend verification email

**Request Body**: `ResendBody`
```json
{
  "email": "user@example.com"
}
```

**Response**: `MessageResponse` (200)

**Rate Limiting**: Cooldown period (default: 60 seconds)

**Implementation Notes**:
- Always returns generic message (prevents user enumeration)
- Checks last verification creation time
- Raises `429` if too soon

---

#### POST /auth/login

**Summary**: Authenticate user and get tokens

**Request Body**: `LoginBody`
```json
{
  "email": "user@example.com",
  "password": "securepass123"
}
```

**Response**: `TokenPair` (200)

**Errors**:
- `401`: Invalid credentials
- `403`: Email not verified

**Implementation Notes**:
- Email normalized to lowercase
- Password verified via `verify_password`
- User must be active and verified
- Default account selected (owner account or first membership)
- Refresh token stored in database

---

#### POST /auth/refresh

**Summary**: Refresh access token

**Query/Form Parameters**:
- `refresh_token` (required): Refresh token

**Response**: `TokenPair` (200)

**Errors**:
- `401`: Invalid/expired/revoked token

**Implementation Notes**:
- Token validated via JWT decode and database lookup
- Token rotated (new jti and hash)
- Existing token row updated (not new row created)
- New access token includes current role

---

#### POST /auth/logout

**Summary**: Revoke refresh token

**Query/Form Parameters**:
- `refresh_token` (required): Refresh token to revoke

**Response**: `{"ok": true}` (200)

**Implementation Notes**:
- Token marked as revoked (`revoked_at` set)
- Token cannot be used after revocation

---

#### GET /auth/me

**Summary**: Get current authenticated user

**Authentication**: Required (Bearer token)

**Response**: `Me` (200)
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "is_active": true,
  "memberships": [...],
  "is_subscribed": false
}
```

**Implementation Notes**:
- Queries memberships with account names
- Determines subscription status from first membership's account
- Handles trial period detection
- Includes testing override for specific emails

---

#### POST /auth/change-password

**Summary**: Change password for logged-in user

**Authentication**: Required

**Request Body**: `ChangePasswordBody`
```json
{
  "current_password": "oldpass",
  "new_password": "newpass123",
  "confirm_new_password": "newpass123"
}
```

**Response**: `MessageResponse` (200)

**Implementation Notes**:
- Verifies current password
- Validates new passwords match
- Updates password hash
- Revokes all refresh tokens (forces re-login)
- Sends confirmation email (best-effort)

---

#### POST /auth/change-name

**Summary**: Update user's first/last name

**Authentication**: Required

**Request Body**: `ChangeNameBody`
```json
{
  "first_name": "Jane",
  "last_name": "Smith"
}
```

**Response**: `MessageResponse` (200)

**Errors**:
- `400`: No name fields provided

---

#### POST /auth/password/forgot

**Summary**: Send password reset email

**Request Body**: `PasswordForgotBody`
```json
{
  "email": "user@example.com"
}
```

**Response**: `MessageResponse` (200)

**Implementation Notes**:
- Always returns generic message (prevents user enumeration)
- Works for email+password and Google-only users
- Creates password reset token

---

#### POST /auth/password/reset

**Summary**: Reset password using token

**Request Body**: `PasswordResetBody`
```json
{
  "token": "reset_token_from_email",
  "new_password": "newpass123"
}
```

**Response**: `MessageResponse` (200)

**Implementation Notes**:
- Validates token (exists, not expired, not used)
- Sets/updates password
- Revokes all refresh tokens
- Sends confirmation email

---

#### GET /auth/google/start

**Summary**: Get Google OAuth authorization URL

**Response**: `GoogleStartOut` (200)
```json
{
  "auth_url": "https://accounts.google.com/o/oauth2/v2/auth?..."
}
```

**Errors**:
- `400`: Google OAuth not configured

---

#### POST /auth/google/callback

**Summary**: Google OAuth callback handler

**Query Parameters**:
- `code` (required): Authorization code from Google

**Response**: `TokenPair` (200)

**Implementation Notes**:
- Exchanges code for tokens via Authlib
- Fetches userinfo from Google
- Creates user if doesn't exist
- Links Google sub to user
- Creates personal workspace if needed
- Issues tokens

**Errors**:
- `400`: Invalid grant, redirect URI mismatch, email not verified

---

### `app/api/routes/accounts.py`

**Prefix**: `/accounts`  
**Tag**: `accounts`

Account and team management endpoints.

#### GET /accounts/{account_id}

**Summary**: Get account details

**Authentication**: Required  
**Permissions**: OWNER, ADMIN

**Response** (200):
```json
{
  "id": "uuid",
  "name": "Account Name"
}
```

---

#### GET /accounts/{account_id}/team_members

**Summary**: List team members and pending invites

**Authentication**: Required  
**Permissions**: OWNER, ADMIN

**Response**: `List[TeamMemberOut]` (200)

**Implementation Notes**:
- Returns active members (ADMIN, MEMBER roles)
- Excludes caller
- Includes pending invites with status (pending/expired)
- Shows schema access for each member

---

#### POST /accounts/{account_id}/invite

**Summary**: Invite team member

**Authentication**: Required  
**Permissions**: OWNER, ADMIN

**Request Body**: `InviteMemberBody`
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

**Implementation Notes**:
- Validates schema IDs belong to account
- Prevents duplicate invites
- Creates invitation with token
- Sends invitation email
- Token expires in 7 days (default)

**Errors**:
- `400`: User already member, pending invite exists, invalid schema IDs

---

#### GET /accounts/invites/{token}

**Summary**: Preview invite (public)

**Authentication**: Not required

**Response** (200):
```json
{
  "email": "invited@example.com",
  "role": "MEMBER",
  "account_id": "uuid"
}
```

**Errors**:
- `404`: Invite not found or expired

---

#### DELETE /accounts/{account_id}/members/{user_id}

**Summary**: Remove team member

**Authentication**: Required  
**Permissions**: OWNER

**Response** (200):
```json
{
  "ok": true
}
```

**Errors**:
- `400`: Cannot remove last OWNER

---

#### DELETE /accounts/{account_id}/users

**Summary**: Delete user and cleanup related records

**Authentication**: Required  
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

**Implementation Notes**:
- Best-effort cleanup (each step isolated)
- Removes invitations
- Reassigns created_by fields to account owner
- Deletes email verifications, password resets, refresh tokens
- Removes membership
- Deletes user row

**Errors**:
- `403`: Cannot delete account owner

---

#### PATCH /accounts/{account_id}

**Summary**: Rename account

**Authentication**: Required  
**Permissions**: OWNER

**Request Body**: `AccountRename`
```json
{
  "name": "New Account Name"
}
```

**Response** (200):
```json
{
  "ok": true,
  "id": "uuid",
  "name": "New Account Name"
}
```

---

#### PUT /accounts/{account_id}/members/permissions

**Summary**: Update member permissions

**Authentication**: Required  
**Permissions**: OWNER, ADMIN

**Request Body**: `MemberUpdatePermissions`
```json
{
  "user_id": "uuid",
  "role": "MEMBER",
  "manage_schema_ids": ["uuid1", "uuid2"]
}
```

**Response** (200):
```json
{
  "ok": true,
  "message": "Permissions updated"
}
```

**Implementation Notes**:
- Can use `user_id` or `email`
- Updates membership or pending invites
- Validates schema IDs belong to account
- Prevents promoting to OWNER via API
- Clears per-schema permissions for ADMIN/OWNER roles

**Errors**:
- `403`: Promoting to OWNER not allowed
- `400`: Cannot demote last OWNER

---

### `app/api/routes/schemas.py`

**Prefix**: `/accounts/{account_id}/schemas`  
**Tag**: `schemas`

Schema CRUD operations.

#### POST /accounts/{account_id}/schemas

**Summary**: Create schema

**Authentication**: Required  
**Permissions**: OWNER, ADMIN

**Request Body**: `SchemaSpecCreate`
```json
{
  "schema_name": "Customer Schema",
  "schema": {
    "columns": [
      {"name": "email", "type": "string"},
      {"name": "age", "type": "integer"}
    ]
  },
  "validators": {
    "email": {"required": true}
  }
}
```

**Response**: `SchemaSpecRead` (200)

**Implementation Notes**:
- Generates default name if not provided ("Schema 1", "Schema 2", etc.)
- Enforces uniqueness per account (case-insensitive)
- Stamps account_id and created_by_user_id

**Errors**:
- `400`: Schema name already exists

---

#### GET /accounts/{account_id}/schemas

**Summary**: List schemas

**Authentication**: Required  
**Permissions**: All roles (visibility-aware)

**Response**: `List[SchemaSpecRead]` (200)

**Implementation Notes**:
- OWNER/ADMIN: See all schemas
- MEMBER/VIEWER: See only schemas in `manage_schema_ids`
- Filters out soft-deleted schemas
- Computes column count from schema JSON
- Formats dates for display

---

#### GET /accounts/{account_id}/schemas/{schema_id}

**Summary**: Get schema by ID

**Authentication**: Required  
**Permissions**: All roles (visibility-aware)

**Response**: `SchemaSpecRead` (200)

**Errors**:
- `404`: Schema not found or not visible

---

#### PUT /accounts/{account_id}/schemas/{schema_id}

**Summary**: Update schema

**Authentication**: Required  
**Permissions**: OWNER, ADMIN

**Request Body**: `SchemaSpecUpdate` (all fields optional)

**Response**: `SchemaSpecRead` (200)

**Implementation Notes**:
- Validates uniqueness if name changed
- Updates only provided fields

---

#### DELETE /accounts/{account_id}/schemas/{schema_id}

**Summary**: Delete schema (soft delete)

**Authentication**: Required  
**Permissions**: OWNER, ADMIN

**Response**: 204 No Content

**Implementation Notes**:
- Soft delete (sets `deleted_at`)
- Deletes associated integrations
- Removes schema_id from member permissions
- Removes schema_id from invitations

---

### `app/api/routes/subscriptions.py`

**Prefix**: `/accounts/{account_id}/subscriptions`  
**Tag**: `subscriptions`

Subscription and billing endpoints.

#### GET /accounts/{account_id}/subscriptions/

**Summary**: Get subscription status

**Authentication**: Required  
**Permissions**: OWNER

**Response**: `SubscriptionRead` (200)

**Implementation Notes**:
- Defaults to FREE plan if no subscription
- Detects trial period
- Formats display status and description
- Includes plan limits and features

---

#### POST /accounts/{account_id}/subscriptions/checkout

**Summary**: Create Stripe Checkout session

**Authentication**: Required  
**Permissions**: OWNER

**Response**: `CheckoutResponse` (200)
```json
{
  "checkout_session_id": "cs_test_...",
  "url": "https://checkout.stripe.com/..."
}
```

**Implementation Notes**:
- Creates Stripe Checkout Session for PRO plan
- Sets 14-day trial period
- Creates/updates local Subscription record (status: pending)
- Includes account_id in metadata

---

#### POST /accounts/{account_id}/subscriptions/portal

**Summary**: Create Stripe Billing Portal session

**Authentication**: Required  
**Permissions**: OWNER

**Response**: `PortalResponse` (200)
```json
{
  "url": "https://billing.stripe.com/..."
}
```

**Errors**:
- `404`: No billing customer found
- `500`: Billing Portal not configured in Stripe

---

### `app/api/routes/integrations.py`

**Prefix**: `/accounts`  
**Tag**: `integrations`

Integration and credential management endpoints.

#### POST /accounts/{account_id}/credentials

**Summary**: Create API credential

**Authentication**: Required  
**Permissions**: OWNER, ADMIN

**Request Body**: `APICredentialCreate`

**Response**: `APICredentialCreateResponse` (200)

**Implementation Notes**:
- Generates client_id (24 chars) and client_secret (40 chars)
- Hashes client_secret before storage
- Returns unhashed secret one-time only
- Enforces unique app_name per account

---

#### GET /accounts/{account_id}/credentials

**Summary**: List credentials

**Authentication**: Required  
**Permissions**: All roles

**Response**: `List[APICredentialOut]` (200)

**Implementation Notes**:
- Filters out revoked credentials
- Does not include client_secret

---

#### PATCH /accounts/{account_id}/credentials/{credential_id}

**Summary**: Update credential metadata

**Authentication**: Required  
**Permissions**: OWNER, ADMIN

**Request Body**: `APICredentialUpdate`

**Response**: `APICredentialOut` (200)

---

#### POST /accounts/{account_id}/credentials/{credential_id}/rotate

**Summary**: Rotate client secret

**Authentication**: Required  
**Permissions**: OWNER, ADMIN

**Response**: `APICredentialRotateResponse` (200)

**Implementation Notes**:
- Generates new client_secret
- Updates hash in database
- Returns new secret one-time only

---

#### DELETE /accounts/{account_id}/credentials/{credential_id}

**Summary**: Delete credential

**Authentication**: Required  
**Permissions**: OWNER, ADMIN, MEMBER

**Response**: 204 No Content

**Implementation Notes**:
- Deletes associated integrations
- Deletes credential

---

#### POST /accounts/{account_id}/integrations

**Summary**: Create integration

**Authentication**: Required  
**Permissions**: All roles (MEMBER restricted to their schemas)

**Request Body**: `IntegrationCreate`

**Response**: `IntegrationOut` (200)

**Implementation Notes**:
- Validates schema and credential belong to account
- MEMBER can only create for schemas in `manage_schema_ids`

**Errors**:
- `400`: Schema or credential not found/invalid

---

#### GET /accounts/{account_id}/integrations

**Summary**: List integrations

**Authentication**: Required  
**Permissions**: All roles (visibility-aware)

**Response**: `List[IntegrationOut]` (200)

**Implementation Notes**:
- OWNER/ADMIN/VIEWER: See all active integrations
- MEMBER: See only integrations for their allowed schemas

---

#### PATCH /accounts/{account_id}/integrations/{integration_id}

**Summary**: Update integration

**Authentication**: Required  
**Permissions**: OWNER, ADMIN

**Request Body**: `IntegrationUpdate`

**Response**: `IntegrationOut` (200)

---

#### POST /accounts/{account_id}/integrations/{integration_id}/usage

**Summary**: Increment usage counter

**Authentication**: Required  
**Permissions**: All roles

**Request Body**: `UsageIncrement`
```json
{
  "amount": 1
}
```

**Response**: `IntegrationOut` (200)

**Implementation Notes**:
- Atomic increment via SQL UPDATE
- Default amount is 1

---

#### POST /accounts/integrations/launch

**Summary**: Launch integration page (server-to-server)

**Authentication**: Via client_id/client_secret

**Request Body**: `IntegrationLaunchRequest`

**Response**: `IntegrationLaunchUrlResponse` (200)

**Implementation Notes**:
- Authenticates via client_id/client_secret
- Validates integration is active
- Creates LaunchToken (short-lived, single-use)
- Encodes overrides into token (base64 JSON)
- Returns frontend URL with token in fragment

**Errors**:
- `401`: Invalid credentials
- `404`: Integration not found or inactive
- `400`: Invalid override keys or missing placeholders

---

#### GET /accounts/integrations/launch/info

**Summary**: Get integration launch info

**Authentication**: Bearer token (launch token)

**Response**: `IntegrationLaunchInfoResponse` (200)

**Implementation Notes**:
- Validates token (not expired, not used)
- Marks token as used
- Decodes overrides from token
- Renders API endpoint template with overrides
- Increments integration usage
- Returns integration details

**Errors**:
- `401`: Invalid or expired token
- `404`: Integration or schema not found

---

### `app/api/routes/mapper.py`

**Prefix**: None  
**Tag**: None

Column mapping endpoint.

#### POST /loci-ai-mapper

**Summary**: Map import columns to schema columns using AI

**Authentication**: Not required

**Request Body**: `LociMapperRequest`
```json
{
  "schema_columns": ["first_name", "last_name", "email"],
  "import_columns": ["fname", "lname", "email_address"],
  "min_confidence": 0.50,
  "model_name": "sentence-transformers/all-MiniLM-L6-v2"
}
```

**Response**: `LociMapperResponse` (200)
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

**Implementation Notes**:
- Uses sentence-transformers for embeddings
- Combines with Jaro-Winkler lexical similarity
- Solves assignment problem (Hungarian algorithm)
- Returns one-to-one matches with confidence scores

**Errors**:
- `500`: Model loading failed (missing dependencies)

---

### `app/api/routes/dashboard.py`

**Prefix**: `/accounts`  
**Tag**: `dashboard`

Dashboard endpoints.

#### GET /accounts/{account_id}/dashboard/kpis

**Summary**: Get dashboard KPIs

**Authentication**: Required  
**Permissions**: All roles

**Response**: `DashboardKPIs` (200)
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

**Implementation Notes**:
- Counts non-deleted schemas
- Sums integration usage
- Returns 3 most recent integrations

---

### `app/api/routes/contact.py`

**Prefix**: None  
**Tag**: None

Public contact form.

#### POST /contact

**Summary**: Submit contact form

**Authentication**: Not required

**Request Body**: `ContactBody`
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

**Response**: `MessageResponse` (200)

**Implementation Notes**:
- Sends email to admin@smartschema.io
- HTML formatted email
- Best-effort (doesn't fail API if email fails)

**Errors**:
- `500`: Failed to send email

---

### `app/api/routes/public_plans.py`

**Prefix**: None  
**Tag**: `public`

Public plans endpoint.

#### GET /plans

**Summary**: List available subscription plans

**Authentication**: Not required

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

**Implementation Notes**:
- Reads from `PLANS` dict in `app/services/billing.py`
- Includes limits and feature flags

---

### `app/api/routes/stripe_webhook.py`

**Prefix**: `/stripe`  
**Tag**: `stripe`

Stripe webhook handler.

#### POST /stripe/webhook

**Summary**: Handle Stripe webhook events

**Authentication**: Via Stripe signature header

**Headers**:
- `stripe-signature`: Stripe webhook signature

**Request Body**: Stripe event JSON

**Response** (200):
```json
{
  "received": true
}
```

**Handled Events**:
- `checkout.session.completed`: Create/update subscription
- `customer.subscription.updated`: Update subscription status
- `customer.subscription.deleted`: Mark subscription canceled
- `invoice.payment_failed`: Mark subscription past_due
- `invoice.payment_succeeded`: Mark subscription active
- `checkout.session.async_payment_failed`: Mark incomplete
- `setup_intent.setup_failed`: Mark incomplete
- `payment_intent.payment_failed`: Mark past_due

**Implementation Notes**:
- Validates Stripe signature
- Idempotent processing via `WebhookEvent` tracking
- Resolves account_id from metadata or customer email
- Fetches subscription from Stripe if needed
- Updates local Subscription record

**Errors**:
- `400`: Invalid webhook signature
- `500`: Webhook secret not configured

---

## Common Patterns

### Authentication

Most routes use `Depends(current_user)` or `Depends(require_role_for_account(...))`:

```python
def endpoint(
    user: User = Depends(current_user),
    db: Session = Depends(get_db)
):
    # user is authenticated
```

### Authorization

Path-based authorization:
```python
def endpoint(
    account_id: UUID,
    tup = Depends(require_role_for_account({Role.OWNER, Role.ADMIN})),
    db: Session = Depends(get_db)
):
    user, account_id, role = tup
    # user has required role for account
```

### Error Handling

Routes raise `HTTPException` for errors:
```python
raise HTTPException(status_code=404, detail="Not found")
```

### Database Transactions

Routes commit changes:
```python
db.add(model)
db.commit()
db.refresh(model)  # Refresh to get computed fields
```

### Response Formatting

Routes format responses using helper functions:
```python
def _format_schema(obj: SchemaSpecification) -> dict:
    # Format dates, compute columns, etc.
    return {...}
```

## Best Practices

1. **Validate Early**: Use Pydantic schemas for request validation
2. **Check Permissions**: Always verify user has required role
3. **Handle Errors**: Return appropriate HTTP status codes
4. **Use Transactions**: Commit related changes together
5. **Format Responses**: Use consistent response formatting
6. **Document Endpoints**: Use docstrings and OpenAPI metadata
7. **Idempotency**: Make operations idempotent where possible
8. **Rate Limiting**: Implement rate limiting for sensitive endpoints


