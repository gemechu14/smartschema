# Core Configuration and Security Documentation

This document provides detailed documentation for core configuration and security utilities in the SmartSchema Backend.

## Core Files

### `app/core/config.py`

Application configuration management.

#### Settings Class

```python
class Settings(BaseModel):
    # Database
    database_url: str
    
    # Application
    app_name: str = "SmartSchema"
    app_base_url: str = "https://app.smartschema.io"
    
    # JWT
    jwt_secret: str
    jwt_issuer: str = "locimapper-api"
    access_ttl_min: int = 15
    refresh_ttl_days: int = 30
    
    # Email (SMTP)
    smtp_server: str
    smtp_port: int = 587
    smtp_user: str
    smtp_password: str
    mail_from: str
    mail_from_name: str = "SmartSchema"
    
    # Google OAuth
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str
    
    # Feature Flags
    invite_exp_days: int = 7
    email_verify_exp_hours: int = 24
    email_verify_resend_cooldown_s: int = 60
    password_reset_exp_hours: int = 24
    launch_token_ttl_seconds: int = 300
```

**Purpose**: Centralized configuration via environment variables

**Environment Variables**:
- `DATABASE_URL`: PostgreSQL connection string
- `APP_NAME`: Application name
- `APP_BASE_URL`: Base URL for frontend
- `JWT_SECRET`: Secret key for JWT signing (CHANGE IN PRODUCTION)
- `JWT_ISSUER`: JWT issuer claim
- `ACCESS_TOKEN_TTL_MIN`: Access token lifetime in minutes
- `REFRESH_TOKEN_TTL_DAYS`: Refresh token lifetime in days
- `SMTP_SERVER`: SMTP server hostname
- `SMTP_PORT`: SMTP port (default: 587)
- `SMTP_USER`: SMTP username
- `SMTP_PASSWORD`: SMTP password
- `MAIL_FROM`: Sender email address
- `MAIL_FROM_NAME`: Sender display name
- `GOOGLE_CLIENT_ID`: Google OAuth client ID
- `GOOGLE_CLIENT_SECRET`: Google OAuth client secret
- `GOOGLE_REDIRECT_URI`: Google OAuth redirect URI
- `INVITE_EXP_DAYS`: Invitation expiration days
- `EMAIL_VERIFY_EXP_HOURS`: Email verification expiration hours
- `EMAIL_VERIFY_RESEND_COOLDOWN_S`: Cooldown for resend verification
- `PASSWORD_RESET_EXP_HOURS`: Password reset expiration hours
- `LAUNCH_TOKEN_TTL_SECONDS`: Launch token lifetime in seconds

**Usage**:
```python
from app.core.config import settings

db_url = settings.database_url
jwt_secret = settings.jwt_secret
```

**Security Notes**:
- `JWT_SECRET` must be strong and unique in production
- Never commit `.env` file to version control
- Use different secrets for development and production

---

### `app/core/security.py`

Security utilities for authentication and encryption.

#### Password Hashing

```python
pwd_ctx = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def hash_password(p: str) -> str:
    return pwd_ctx.hash(p)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)
```

**Purpose**: Secure password hashing and verification

**Algorithm**: PBKDF2 with SHA-256

**Usage**:
```python
# Hash password
password_hash = hash_password("userpassword")

# Verify password
is_valid = verify_password("userpassword", password_hash)
```

**Security**:
- Uses Passlib's CryptContext
- PBKDF2 is secure and slow (prevents brute force)
- Never store plaintext passwords

---

#### JWT Token Functions

```python
def make_access_token(sub: str, account_id: str, role: str) -> str
def make_refresh_token(sub: str, account_id: str, jti: str) -> str
def make_launch_token(integration_id: str, credential_id: str, account_id: str, ttl_seconds: int = 300) -> str
def decode_jwt(token: str) -> dict
```

**Purpose**: Create and decode JWT tokens

**Access Token Payload**:
```json
{
  "iss": "locimapper-api",
  "sub": "user-uuid",
  "aid": "account-uuid",
  "role": "OWNER",
  "iat": 1234567890,
  "exp": 1234568790
}
```

**Refresh Token Payload**:
```json
{
  "iss": "locimapper-api",
  "sub": "user-uuid",
  "aid": "account-uuid",
  "jti": "token-uuid",
  "iat": 1234567890,
  "exp": 1234571490
}
```

**Launch Token Payload**:
```json
{
  "iss": "locimapper-api",
  "int_id": "integration-uuid",
  "cred_id": "credential-uuid",
  "aid": "account-uuid",
  "iat": 1234567890,
  "exp": 1234568190
}
```

**Algorithm**: HS256 (HMAC-SHA256)

**Usage**:
```python
# Create access token
access_token = make_access_token(
    sub=str(user.id),
    account_id=str(account.id),
    role=role.value
)

# Decode token
payload = decode_jwt(access_token)
user_id = payload.get("sub")
```

**Security**:
- Tokens signed with `JWT_SECRET`
- Expiration enforced via `exp` claim
- Issuer validated via `iss` claim
- Refresh tokens stored in database for revocation

---

#### Token Generation

```python
def random_token(n_bytes: int = 32) -> str
def sha256(s: str) -> str
```

**Purpose**: Generate secure random tokens and hashes

**random_token()**:
- Generates URL-safe base64 token
- Uses `os.urandom()` for cryptographically secure randomness
- Strips padding (`=`) for cleaner URLs

**sha256()**:
- Computes SHA-256 hash of string
- Used for token hashing (verification tokens, refresh tokens)

**Usage**:
```python
# Generate random token
token = random_token(32)  # 32 bytes = ~43 characters

# Hash token
token_hash = sha256(token)
```

**Security**:
- `os.urandom()` is cryptographically secure
- SHA-256 is one-way (cannot reverse hash)
- Tokens stored as hashes in database

---

#### Time Utilities

```python
def now_utc() -> datetime
def ensure_aware(dt: datetime) -> datetime
```

**Purpose**: Timezone-aware datetime utilities

**now_utc()**:
- Returns current UTC datetime with timezone
- Used for all timestamp operations

**ensure_aware()**:
- Converts naive datetime to timezone-aware UTC
- Handles None values gracefully

**Usage**:
```python
# Get current time
now = now_utc()

# Ensure timezone-aware
dt = ensure_aware(naive_dt)
```

**Best Practices**:
- Always use UTC for storage
- Convert to user timezone only for display
- Use `ensure_aware()` when comparing datetimes

---

#### Name Parsing

```python
def parse_name_from_email(email: str) -> Tuple[Optional[str], Optional[str]]
```

**Purpose**: Extract first/last name from email address

**Algorithm**:
- Splits email local-part on `.`, `_`, or `-`
- Capitalizes first part as first name
- Capitalizes last part as last name
- Returns single name if only one part

**Example**:
```python
first, last = parse_name_from_email("john.doe@example.com")
# Returns: ("John", "Doe")

first, last = parse_name_from_email("johndoe@example.com")
# Returns: ("Johndoe", None)
```

---

### `app/api/deps.py`

Database dependency injection.

#### get_db()

```python
def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**Purpose**: FastAPI dependency for database sessions

**Usage**:
```python
from app.api.deps import get_db

def endpoint(db: Session = Depends(get_db)):
    # Use db session
    users = db.query(User).all()
    # Session automatically closed after request
```

**Lifecycle**:
1. Creates session at request start
2. Yields session to route handler
3. Closes session after request completes (even on error)

**Best Practices**:
- Always use `Depends(get_db)` in routes
- Don't manually create sessions
- Session automatically handles transactions

---

### `app/api/deps_auth.py`

Authentication dependencies.

#### current_user()

```python
def current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> User
```

**Purpose**: Authenticate user from Bearer token

**Usage**:
```python
from app.api.deps_auth import current_user

def endpoint(user: User = Depends(current_user)):
    # user is authenticated and active
    user_id = user.id
```

**Validation**:
1. Extracts Bearer token from Authorization header
2. Decodes JWT token
3. Looks up user by ID from token
4. Verifies user is active and email verified
5. Returns User object

**Errors**:
- `401`: Missing/invalid token, user not found, token expired
- `403`: User inactive or email not verified

---

#### require_role_for_account()

```python
def require_role_for_account(allowed: Iterable[Role]):
    def dep(
        account_id: UUID,
        user: User = Depends(current_user),
        db: Session = Depends(get_db),
    ) -> Tuple[User, UUID, Role]:
        # Check membership and role
        # Return (user, account_id, role) if allowed
        # Raise 403 if not allowed
```

**Purpose**: Path-based authorization dependency

**Usage**:
```python
from app.api.deps_auth import require_role_for_account
from app.models.auth_models import Role

def endpoint(
    account_id: UUID,
    tup = Depends(require_role_for_account({Role.OWNER, Role.ADMIN})),
    db: Session = Depends(get_db)
):
    user, account_id, role = tup
    # User has OWNER or ADMIN role for account
```

**Validation**:
1. Authenticates user via `current_user`
2. Looks up membership for user + account
3. Checks role is in allowed set
4. Returns tuple of (user, account_id, role)

**Errors**:
- `403`: Not a member of account or insufficient role

**Benefits**:
- Reusable across routes
- Consistent authorization logic
- Returns user, account, and role for use in route

---

## Security Best Practices

### Password Security

1. **Never store plaintext**: Always hash passwords
2. **Use strong hashing**: PBKDF2 or bcrypt
3. **Salt automatically**: Passlib handles salting
4. **Minimum length**: Enforce minimum password length (6+ chars)
5. **Password reset**: Revoke all tokens on password change

### Token Security

1. **Strong secret**: Use cryptographically random JWT secret
2. **Short expiration**: Access tokens expire quickly (15 min)
3. **Token rotation**: Rotate refresh tokens on use
4. **Token revocation**: Store refresh tokens for revocation
5. **HTTPS only**: Always use HTTPS in production
6. **Token storage**: Don't store tokens in localStorage (use httpOnly cookies)

### Authentication

1. **Email verification**: Require email verification before login
2. **Rate limiting**: Limit login attempts per IP
3. **Account lockout**: Lock accounts after failed attempts
4. **Session management**: Track active sessions
5. **Logout**: Revoke tokens on logout

### Authorization

1. **Principle of least privilege**: Grant minimum required permissions
2. **Role-based access**: Use RBAC for authorization
3. **Path-based checks**: Verify permissions at route level
4. **Resource ownership**: Verify resource belongs to account
5. **Audit logging**: Log authorization decisions

### Data Security

1. **Input validation**: Validate all inputs via Pydantic
2. **SQL injection**: Use ORM, never raw SQL with user input
3. **XSS prevention**: Sanitize user input, use proper content types
4. **CSRF protection**: Use CSRF tokens for state-changing operations
5. **Data encryption**: Encrypt sensitive data at rest

### API Security

1. **HTTPS**: Always use HTTPS in production
2. **CORS**: Configure CORS for specific origins
3. **Rate limiting**: Implement rate limiting
4. **Request size limits**: Limit request body size
5. **Error messages**: Don't leak sensitive info in errors

## Configuration Security

### Environment Variables

1. **Never commit**: Never commit `.env` files
2. **Use secrets**: Use secret management in production
3. **Rotate secrets**: Rotate secrets regularly
4. **Separate environments**: Use different secrets per environment
5. **Documentation**: Document all required environment variables

### Secrets Management

**Development**:
- Use `.env` file (gitignored)
- Use weak secrets (acceptable for local dev)

**Production**:
- Use environment variables or secret manager
- Use strong, randomly generated secrets
- Rotate secrets periodically
- Never log secrets

## Common Security Issues

### 1. Weak JWT Secret

**Problem**: Using default or weak JWT secret

**Solution**: Generate strong random secret:
```python
import secrets
jwt_secret = secrets.token_urlsafe(32)
```

### 2. Token in URL

**Problem**: Passing tokens in URL query parameters

**Solution**: Use Authorization header or URL fragment (for launch tokens)

### 3. Missing Email Verification

**Problem**: Allowing login without email verification

**Solution**: Always check `email_verified_at` before login

### 4. SQL Injection

**Problem**: Using raw SQL with user input

**Solution**: Always use SQLAlchemy ORM or parameterized queries

### 5. CORS Misconfiguration

**Problem**: Allowing all origins (`allow_origins=["*"]`)

**Solution**: Specify exact allowed origins

## Security Checklist

- [ ] Strong JWT secret configured
- [ ] HTTPS enabled in production
- [ ] CORS configured for specific origins
- [ ] Email verification required
- [ ] Password reset revokes tokens
- [ ] Rate limiting implemented
- [ ] Input validation on all endpoints
- [ ] SQL injection prevention (ORM usage)
- [ ] XSS prevention (proper content types)
- [ ] Error messages don't leak info
- [ ] Secrets not in code or logs
- [ ] Database credentials secure
- [ ] SMTP credentials secure
- [ ] Stripe webhook signature validated
- [ ] Token expiration enforced
- [ ] Refresh token rotation enabled


