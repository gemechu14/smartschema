# Database Models Documentation

This document provides detailed documentation for all SQLAlchemy database models in the SmartSchema Backend.

## Overview

All models inherit from `Base` defined in `app/db/base.py` and use PostgreSQL-specific types (UUID, JSONB). Models are registered in `app/db/model_registry.py` for Alembic migrations.

## Model Files

### `app/models/auth_models.py`

Contains authentication and account management models.

#### Role Enum

```python
class Role(str, Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"
    VIEWER = "VIEWER"
```

**Purpose**: Defines user roles for RBAC (Role-Based Access Control)

**Usage**: Used in Membership model and throughout authorization logic

---

#### User Model

```python
class User(Base):
    __tablename__ = "users"
    
    id: UUID (primary key)
    email: String(320) (unique, indexed, not null)
    first_name: String(120) (nullable)
    last_name: String(120) (nullable)
    password_hash: String(255) (nullable)
    google_sub: String(128) (nullable, unique)
    is_active: Boolean (default: False, not null)
    email_verified_at: DateTime(timezone=True) (nullable)
    created_at: DateTime(timezone=True) (default: utcnow, not null)
```

**Purpose**: Represents a user account in the system

**Relationships**:
- One-to-many with `Membership` (via `memberships` relationship)
- One-to-many with `RefreshToken`
- One-to-many with `EmailVerification`
- One-to-many with `PasswordReset`
- One-to-one with `Account` (as owner)

**Key Fields**:
- `email`: Used as username, must be unique, stored lowercase
- `password_hash`: Nullable to support Google OAuth-only users
- `google_sub`: Google OAuth subject identifier
- `is_active`: Must be True to login
- `email_verified_at`: Must be set for account activation

**Constraints**:
- Unique email constraint
- Unique google_sub constraint

**Example Usage**:
```python
user = User(
    email="user@example.com",
    password_hash=hash_password("password"),
    first_name="John",
    last_name="Doe",
    is_active=False
)
db.add(user)
db.commit()
```

---

#### Account Model

```python
class Account(Base):
    __tablename__ = "accounts"
    
    id: UUID (primary key)
    name: String(255) (not null)
    owner_user_id: UUID (foreign key → users.id, not null)
    created_at: DateTime (default: utcnow, not null)
```

**Purpose**: Represents a workspace/tenant account

**Relationships**:
- Many-to-one with `User` (via `owner_user_id`)
- One-to-many with `Membership` (via `members` relationship)
- One-to-many with `SchemaSpecification`
- One-to-many with `Subscription`
- One-to-many with `APICredential`
- One-to-many with `Integration`

**Key Fields**:
- `name`: Human-readable account name (e.g., "John's workspace")
- `owner_user_id`: User who owns this account

**Constraints**:
- Unique constraint on `owner_user_id` (one account per owner)

**Example Usage**:
```python
account = Account(
    name="John's workspace",
    owner_user_id=user.id
)
db.add(account)
db.commit()
```

---

#### Membership Model

```python
class Membership(Base):
    __tablename__ = "memberships"
    
    id: UUID (primary key)
    account_id: UUID (foreign key → accounts.id, not null)
    user_id: UUID (foreign key → users.id, not null)
    role: Role Enum (not null, default: MEMBER)
    manage_schema_ids: JSONB (nullable)
    created_at: DateTime (default: utcnow, not null)
```

**Purpose**: Links users to accounts with role and permissions

**Relationships**:
- Many-to-one with `Account` (via `account` relationship)
- Many-to-one with `User` (via `user` relationship)

**Key Fields**:
- `role`: RBAC role (OWNER, ADMIN, MEMBER, VIEWER)
- `manage_schema_ids`: List of schema UUIDs that MEMBER/VIEWER can access (JSONB array)

**Constraints**:
- Unique constraint on (`account_id`, `user_id`)

**Permissions**:
- OWNER/ADMIN: Full access to all schemas (manage_schema_ids ignored)
- MEMBER/VIEWER: Access only to schemas listed in `manage_schema_ids`

**Example Usage**:
```python
membership = Membership(
    account_id=account.id,
    user_id=user.id,
    role=Role.MEMBER,
    manage_schema_ids=["schema-uuid-1", "schema-uuid-2"]
)
db.add(membership)
db.commit()
```

---

#### Invitation Model

```python
class Invitation(Base):
    __tablename__ = "invitations"
    
    id: UUID (primary key)
    account_id: UUID (foreign key → accounts.id, not null)
    email: String(320) (not null)
    role: Role Enum (not null, default: MEMBER)
    token_hash: String(128) (unique, not null)
    expires_at: DateTime (not null)
    accepted_at: DateTime (nullable)
    manage_schema_ids: JSONB (nullable)
    created_at: DateTime (default: utcnow, not null)
```

**Purpose**: Represents pending invitations to join an account

**Key Fields**:
- `email`: Email address of invitee
- `token_hash`: SHA256 hash of invitation token
- `expires_at`: Expiration timestamp
- `accepted_at`: Set when invitation is accepted
- `manage_schema_ids`: Schema permissions to apply on acceptance

**Constraints**:
- Unique `token_hash` constraint

**Lifecycle**:
1. Created with `expires_at` set (default: 7 days)
2. Email sent with token
3. User signs up with token → `accepted_at` set
4. Membership created with role and permissions

**Example Usage**:
```python
token = random_token(32)
invitation = Invitation(
    account_id=account.id,
    email="newuser@example.com",
    role=Role.MEMBER,
    token_hash=sha256(token),
    expires_at=now_utc() + timedelta(days=7),
    manage_schema_ids=["schema-uuid-1"]
)
db.add(invitation)
db.commit()
```

---

#### RefreshToken Model

```python
class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    
    id: UUID (primary key)
    user_id: UUID (foreign key → users.id, not null)
    account_id: UUID (foreign key → accounts.id, not null)
    jti: String(64) (not null, indexed)
    token_hash: String(128) (not null, unique)
    user_agent: String(255) (nullable)
    ip: String(64) (nullable)
    expires_at: DateTime (not null)
    revoked_at: DateTime (nullable)
    created_at: DateTime (default: utcnow, not null)
```

**Purpose**: Stores refresh tokens for token rotation and revocation

**Key Fields**:
- `jti`: JWT ID (unique identifier for token)
- `token_hash`: SHA256 hash of refresh token
- `user_agent`: Browser/client user agent
- `ip`: Client IP address
- `expires_at`: Token expiration timestamp
- `revoked_at`: Set when token is revoked (logout, password change)

**Token Rotation**:
- On refresh, existing token row is updated with new `jti` and `token_hash`
- Prevents database bloat from creating new rows

**Example Usage**:
```python
refresh_token = RefreshToken(
    user_id=user.id,
    account_id=account.id,
    jti=str(uuid4()),
    token_hash=sha256(token),
    expires_at=now_utc() + timedelta(days=30)
)
db.add(refresh_token)
db.commit()
```

---

### `app/models/schema_spec.py`

#### SchemaSpecification Model

```python
class SchemaSpecification(Base):
    __tablename__ = "schema_specifications"
    
    id: UUID (primary key)
    schema_name: String (not null)
    description: String (nullable)
    schema: JSONB (not null)
    validators: JSONB (not null)
    created_at: DateTime(timezone=True) (server default: now(), not null)
    updated_at: DateTime(timezone=True) (on update: now())
    deleted_at: DateTime(timezone=True) (nullable)
    account_id: UUID (foreign key → accounts.id, CASCADE delete, indexed, not null)
    created_by_user_id: UUID (foreign key → users.id, SET NULL on delete, indexed, nullable)
```

**Purpose**: Stores data schema definitions with validation rules

**Relationships**:
- Many-to-one with `Account` (via `account_id`)
- Many-to-one with `User` (via `created_by_user_id`, nullable)
- One-to-many with `Integration` (via `schema_id`)

**Key Fields**:
- `schema`: JSON object with `columns` array (e.g., `{"columns": [{"name": "email", "type": "string"}]}`)
- `validators`: JSON object mapping column names to validation rules
- `deleted_at`: Soft delete timestamp (null = active)

**Schema Structure**:
```json
{
  "columns": [
    {"name": "first_name", "type": "string"},
    {"name": "email", "type": "string"},
    {"name": "age", "type": "integer"}
  ]
}
```

**Validators Structure**:
```json
{
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
```

**Soft Delete**:
- When deleted, `deleted_at` is set
- Queries filter out deleted schemas: `filter(SchemaSpecification.deleted_at == None)`
- Deleted schemas removed from member permissions

**Example Usage**:
```python
schema = SchemaSpecification(
    schema_name="Customer Schema",
    description="Customer data",
    schema={
        "columns": [
            {"name": "email", "type": "string"},
            {"name": "age", "type": "integer"}
        ]
    },
    validators={
        "email": {"required": True, "unique": True}
    },
    account_id=account.id,
    created_by_user_id=user.id
)
db.add(schema)
db.commit()
```

---

### `app/models/subscription.py`

#### Subscription Model

```python
class Subscription(Base):
    __tablename__ = "subscriptions"
    
    id: UUID (primary key)
    account_id: UUID (foreign key → accounts.id, CASCADE delete, indexed, not null)
    stripe_customer_id: String(255) (nullable)
    stripe_subscription_id: String(255) (nullable)
    plan: String(64) (not null)  # 'FREE' or 'PRO'
    status: String(64) (not null)  # canonical status
    raw_stripe_status: String(64) (nullable)  # exact Stripe status
    last_stripe_event_id: String(255) (nullable)
    current_period_end: DateTime(timezone=True) (nullable)
    trial_ends_at: DateTime(timezone=True) (nullable)
    created_at: DateTime(timezone=True) (server default: now(), not null)
```

**Purpose**: Tracks subscription status for accounts

**Relationships**:
- Many-to-one with `Account` (via `account_id`)

**Key Fields**:
- `plan`: "FREE" or "PRO"
- `status`: Canonical status (active, past_due, canceled, etc.)
- `raw_stripe_status`: Original Stripe status for audit
- `current_period_end`: End of current billing period
- `trial_ends_at`: End of trial period (14 days for PRO)

**Status Values**:
- `active`: Subscription is active
- `trialing`: On trial period
- `past_due`: Payment failed
- `canceled`: Subscription canceled
- `incomplete`: Initial payment failed

**Example Usage**:
```python
subscription = Subscription(
    account_id=account.id,
    plan="PRO",
    status="active",
    stripe_customer_id="cus_123",
    stripe_subscription_id="sub_123",
    current_period_end=datetime(2025, 1, 14),
    trial_ends_at=datetime(2024, 12, 28)
)
db.add(subscription)
db.commit()
```

---

#### WebhookEvent Model

```python
class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    
    id: UUID (primary key)
    event_id: String(255) (unique, indexed, not null)
    processed_at: DateTime(timezone=True) (server default: now(), not null)
```

**Purpose**: Tracks processed Stripe webhook events for idempotency

**Key Fields**:
- `event_id`: Stripe event ID (e.g., "evt_1234567890")

**Idempotency**:
- Prevents processing the same webhook event twice
- Checked before processing: `db.query(WebhookEvent).filter(WebhookEvent.event_id == ev_id).first()`

**Example Usage**:
```python
event = WebhookEvent(event_id="evt_1234567890")
db.add(event)
db.commit()
```

---

### `app/models/integrations.py`

#### APICredential Model

```python
class APICredential(Base):
    __tablename__ = "app_credentials"
    
    id: UUID (primary key)
    account_id: UUID (foreign key → accounts.id, not null)
    created_by: UUID (foreign key → users.id, nullable)
    client_id: String (unique, not null)
    client_secret_hash: String (not null)
    client_secret_expires_at: DateTime (nullable)
    app_name: String (not null)
    authorized_js_origins: JSONB (not null)
    theme: JSONB (nullable)
    created_at: DateTime (default: utcnow)
    revoked: Boolean (default: False)
```

**Purpose**: Stores API credentials for integrations

**Relationships**:
- Many-to-one with `Account` (via `account_id`)
- Many-to-one with `User` (via `created_by`)
- One-to-many with `Integration` (via `credential_id`)
- One-to-many with `LaunchToken` (via `credential_id`)

**Key Fields**:
- `client_id`: Public identifier (24 chars, base64 URL-safe)
- `client_secret_hash`: SHA256 hash of secret (never stored in plaintext)
- `client_secret_expires_at`: Optional expiration (null = never expires)
- `authorized_js_origins`: List of allowed JavaScript origins
- `theme`: Theme customization (colors, logo, labels)

**Constraints**:
- Unique constraint on (`account_id`, `app_name`)

**Security**:
- Client secret shown only once on creation/rotation
- Stored as hash, cannot be retrieved later

**Example Usage**:
```python
credential = APICredential(
    account_id=account.id,
    created_by=user.id,
    client_id=random_token(24),
    client_secret_hash=sha256(secret),
    app_name="My Web App",
    authorized_js_origins=["https://myapp.com"],
    theme={"primary_color": "#0f172a"}
)
db.add(credential)
db.commit()
```

---

#### Integration Model

```python
class Integration(Base):
    __tablename__ = "integrations"
    
    id: UUID (primary key)
    account_id: UUID (foreign key → accounts.id, not null)
    created_by: UUID (foreign key → users.id, nullable)
    name: String (not null)
    description: String (nullable)
    schema_id: UUID (foreign key → schema_specifications.id, not null)
    redirect_url: String (nullable)
    credential_id: UUID (foreign key → app_credentials.id, not null)
    api_endpoint: String (nullable)
    api_headers: JSONB (nullable)
    method: String (nullable)
    behavior: JSONB (nullable)
    created_at: DateTime (default: utcnow)
    active: Boolean (default: True)
    usage: Integer (default: 0)
```

**Purpose**: Maps schemas to external API endpoints for data submission

**Relationships**:
- Many-to-one with `Account` (via `account_id`)
- Many-to-one with `User` (via `created_by`)
- Many-to-one with `SchemaSpecification` (via `schema_id`)
- Many-to-one with `APICredential` (via `credential_id`)
- One-to-many with `LaunchToken` (via `integration_id`)

**Key Fields**:
- `schema_id`: Schema this integration maps to
- `credential_id`: API credential used for authentication
- `api_endpoint`: Backend API URL (supports template variables like `{user_id}`)
- `api_headers`: Static headers for API calls
- `method`: HTTP method (default: "POST")
- `behavior`: Configuration flags (require_all, allow_partial, auto_submit)
- `usage`: Counter for integration invocations

**Template Variables**:
- API endpoint can contain placeholders: `https://api.example.com/users/{user_id}`
- Overrides provided in launch request fill placeholders

**Example Usage**:
```python
integration = Integration(
    account_id=account.id,
    created_by=user.id,
    name="Customer Import",
    schema_id=schema.id,
    credential_id=credential.id,
    api_endpoint="https://api.myapp.com/customers",
    api_headers={"Authorization": "Bearer TOKEN"},
    method="POST",
    behavior={"require_all": True, "auto_submit": False}
)
db.add(integration)
db.commit()
```

---

### `app/models/verification.py`

#### EmailVerification Model

```python
class EmailVerification(Base):
    __tablename__ = "email_verifications"
    
    id: UUID (primary key)
    user_id: UUID (foreign key → users.id, CASCADE delete, indexed, not null)
    token_hash: String(128) (unique, not null)
    expires_at: DateTime(timezone=True) (not null)
    consumed_at: DateTime(timezone=True) (nullable)
    created_at: DateTime(timezone=True) (default: utcnow, not null)
```

**Purpose**: Tracks email verification tokens

**Relationships**:
- Many-to-one with `User` (via `user_id`)

**Key Fields**:
- `token_hash`: SHA256 hash of verification token
- `expires_at`: Expiration timestamp (default: 24 hours)
- `consumed_at`: Set when token is used

**Lifecycle**:
1. Created on signup
2. Email sent with token
3. User clicks link → `consumed_at` set, user activated

**Example Usage**:
```python
verification = EmailVerification(
    user_id=user.id,
    token_hash=sha256(token),
    expires_at=now_utc() + timedelta(hours=24)
)
db.add(verification)
db.commit()
```

---

### `app/models/password_reset.py`

#### PasswordReset Model

```python
class PasswordReset(Base):
    __tablename__ = "password_resets"
    
    id: UUID (primary key)
    user_id: UUID (foreign key → users.id, CASCADE delete, indexed, not null)
    token_hash: String(128) (unique, not null)
    expires_at: DateTime(timezone=True) (not null)
    consumed_at: DateTime(timezone=True) (nullable)
    created_at: DateTime(timezone=True) (default: utcnow, not null)
```

**Purpose**: Tracks password reset tokens

**Relationships**:
- Many-to-one with `User` (via `user_id`)

**Key Fields**:
- `token_hash`: SHA256 hash of reset token
- `expires_at`: Expiration timestamp (default: 24 hours)
- `consumed_at`: Set when token is used

**Lifecycle**:
1. Created on password forgot request
2. Email sent with token
3. User resets password → `consumed_at` set, all refresh tokens revoked

**Example Usage**:
```python
reset = PasswordReset(
    user_id=user.id,
    token_hash=sha256(token),
    expires_at=now_utc() + timedelta(hours=24)
)
db.add(reset)
db.commit()
```

---

### `app/models/launch_token.py`

#### LaunchToken Model

```python
class LaunchToken(Base):
    __tablename__ = "launch_tokens"
    
    id: UUID (primary key)
    token_hash: String (unique, not null)
    integration_id: UUID (not null)
    credential_id: UUID (not null)
    account_id: UUID (not null)
    expires_at: DateTime (not null)
    used: Boolean (default: False)
    created_at: DateTime (default: utcnow)
```

**Purpose**: Short-lived tokens for launching integration pages

**Key Fields**:
- `token_hash`: SHA256 hash of launch token
- `integration_id`: Integration to launch
- `credential_id`: Credential used for authentication
- `account_id`: Account context
- `expires_at`: Expiration timestamp (default: 5 minutes)
- `used`: Set when token is consumed

**Lifecycle**:
1. Created on integration launch request
2. Token embedded in frontend URL fragment
3. Frontend calls info endpoint → `used` set to True

**Security**:
- Short TTL (5 minutes)
- Single-use (marked consumed on first use)
- Token in URL fragment (not sent to server in HTTP request)

**Example Usage**:
```python
launch_token = LaunchToken(
    token_hash=sha256(token),
    integration_id=integration.id,
    credential_id=credential.id,
    account_id=account.id,
    expires_at=now_utc() + timedelta(seconds=300)
)
db.add(launch_token)
db.commit()
```

---

## Common Patterns

### UUID Primary Keys

All models use UUID primary keys:
```python
id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
```

### Timestamps

- `created_at`: Set on creation (default: `datetime.utcnow`)
- `updated_at`: Set on update (via `onupdate`)
- Timezone-aware timestamps use `DateTime(timezone=True)`

### Soft Deletes

Some models use soft deletes:
- `SchemaSpecification.deleted_at`: Soft delete for schemas
- Queries filter: `filter(Model.deleted_at == None)`

### Foreign Key Cascades

- `ondelete="CASCADE"`: Delete child records when parent deleted
- `ondelete="SET NULL"`: Set foreign key to NULL when parent deleted

### JSONB Fields

Used for flexible schema:
- `Membership.manage_schema_ids`: Array of UUIDs
- `SchemaSpecification.schema`: Schema definition
- `SchemaSpecification.validators`: Validation rules
- `Integration.behavior`: Configuration flags
- `APICredential.theme`: Theme customization

## Indexes

Indexes are defined on:
- Foreign keys (for join performance)
- Frequently queried fields (`email`, `token_hash`, `jti`)
- Unique constraints automatically create indexes

## Best Practices

1. **Always use relationships**: Use SQLAlchemy relationships instead of manual joins
2. **Filter soft deletes**: Always filter `deleted_at == None` for soft-deleted models
3. **Use transactions**: Wrap related operations in transactions
4. **Validate before save**: Use Pydantic schemas for validation before creating models
5. **Hash sensitive data**: Never store passwords or secrets in plaintext


