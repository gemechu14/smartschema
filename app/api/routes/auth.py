from datetime import timedelta
from uuid import uuid4, UUID
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from sqlalchemy.orm import Session
from authlib.integrations.requests_client import OAuth2Session
from sqlalchemy.exc import IntegrityError
from app.api.deps import get_db
from app.api.deps_auth import current_user
from urllib.parse import unquote
from app.core.config import settings
from app.core.security import (
    hash_password, verify_password, make_access_token, make_refresh_token,
    sha256, parse_name_from_email, now_utc, decode_jwt, ensure_aware
)
from app.services.billing import canonicalize_status
from app.models.auth_models import User, Account, Membership, Role, Invitation, RefreshToken
from app.models.verification import EmailVerification
from app.models.password_reset import PasswordReset
from app.api.routes.auth_utils import issue_password_reset

from app.schemas.auth import MembershipOut, PasswordForgotBody, PasswordResetBody, MessageResponse, RoleEnum
from app.api.routes.auth_utils import issue_email_verification
from app.schemas.auth import (
    SignupBody, SignupResponse, VerifyResponse,
    ResendBody, MessageResponse
)

from app.schemas.auth import SignupBody, LoginBody, TokenPair, Me, GoogleStartOut
from app.services.mailer import send_email
import jwt
from app.api.routes.auth_utils import clean_name, names_from_google_userinfo


router = APIRouter(prefix="/auth", tags=["auth"])

# ---- helpers ----

def issue_tokens(db: Session, user: User, account_id: UUID, user_agent: str = "", ip: str = "") -> TokenPair:
    jti = str(uuid4())
    access = make_access_token(str(user.id), str(account_id), _get_role(db, user.id, account_id).value)
    refresh = make_refresh_token(str(user.id), str(account_id), jti)
    rt = RefreshToken(
        user_id=user.id, account_id=account_id, jti=jti,
        token_hash=sha256(refresh),
        user_agent=user_agent[:255] if user_agent else None,
        ip=ip[:64] if ip else None,
        expires_at=now_utc() + timedelta(days=settings.refresh_ttl_days),
    )
    db.add(rt); db.commit()
    return TokenPair(access_token=access, refresh_token=refresh)

def _get_role(db: Session, user_id: UUID, account_id: UUID) -> Role:
    mem = db.query(Membership).filter(Membership.user_id==user_id, Membership.account_id==account_id).first()
    return mem.role if mem else Role.VIEWER

def _consume_invite(db: Session, invite_token: Optional[str]) -> Optional[Invitation]:
    if not invite_token:
        return None
    token_hash = sha256(invite_token)
    inv = db.query(Invitation).filter(Invitation.token_hash==token_hash).first()
    if not inv:
        raise HTTPException(400, "Invalid invite token")
    if inv.accepted_at is not None or inv.expires_at < now_utc():
        raise HTTPException(400, "Invite expired or already used")
    return inv

def _send_verification_email(user: User):
    # stateless signed token with short TTL
    payload = {
        "sub": str(user.id),
        "type": "verify_email",
        "exp": int((now_utc() + timedelta(hours=settings.email_verify_exp_hours)).timestamp()),
        "iss": settings.jwt_issuer
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    link = f"{settings.app_base_url}/auth/verify-email?token={token}"
    html = f"""
    <p>Hi {user.first_name or ''},</p>
    <p>Please verify your email for Locimapper:</p>
    <p><a href="{link}">{link}</a></p>
    """
    send_email(user.email, "Verify your email", html, from_name=settings.mail_from_name)

def _unique_account_name(db: Session, email: str, fn: Optional[str], ln: Optional[str]) -> str:
    base_local = email.split("@")[0]
    base = (fn or base_local).capitalize()
    # e.g., "Alice's Workspace"
    candidate = f"{base}'s Workspace"
    i = 2
    from app.models.auth_models import Account
    existing = {name for (name,) in db.query(Account.name).all()}
    while candidate in existing:
        candidate = f"{base}'s Workspace {i}"
        i += 1
    return candidate

# ---- endpoints ----

# ---------- SIGNUP ----------
@router.post(
    "/signup",
    response_model=SignupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create user and send verification email",
    description="""
Create a user with **unique email (username)**.

If `invite` token is valid → joins invited account with that role.
Otherwise a **new account** is created and the user becomes **OWNER**.

Sends a verification email. Login is blocked until verified.
""",
)
def signup(body: SignupBody, db: Session = Depends(get_db)):
    email = body.email.lower().strip()

    # Unique username/email
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="Email is already registered.")

    # Names from email if missing
    first_name = body.first_name
    last_name = body.last_name
    if not (first_name and last_name):
        fn, ln = parse_name_from_email(email)
        first_name = first_name or fn
        last_name = last_name or ln

    # Create user
    user = User(
        email=email,
        password_hash=hash_password(body.password),
        first_name=first_name,
        last_name=last_name,
        is_active=False,
        email_verified_at=None,
    )
    db.add(user)
    db.flush()  # user.id

    # Invite flow or create new account
    account_id = None
    role = Role.MEMBER
    if body.invite:
        inv = db.query(Invitation).filter(Invitation.token_hash == sha256(body.invite)).first()
        if inv and inv.accepted_at is None and ensure_aware(inv.expires_at) > now_utc():
            account_id = inv.account_id
            role = inv.role
            inv.accepted_at = now_utc()

    if account_id is None:
        # self-owned workspace
        base = (first_name or email.split("@")[0]).strip()
        acct = Account(name=f"{base}'s workspace", owner_user_id=user.id)
        db.add(acct); db.flush()
        account_id = acct.id
        db.add(Membership(account_id=account_id, user_id=user.id, role=Role.OWNER))
    else:
        db.add(Membership(account_id=account_id, user_id=user.id, role=role))

    if body.invite and inv and inv.manage_schema_ids:
        mem = db.query(Membership).filter(
            Membership.account_id == account_id,
            Membership.user_id == user.id
        ).first()
        if mem:
            mem.manage_schema_ids = inv.manage_schema_ids
    # Send verification
    try:
        issue_email_verification(db, user.id, email, first_name)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not create verification token.")
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to send verification email.")

    return SignupResponse()

# ---------- VERIFY ----------
@router.get(
    "/verify",
    response_model=VerifyResponse,
    summary="Verify email using token sent to the user",
    description="Pass the `token` from the verification link to activate the account."
)
def verify_email(
    token: str = Query(..., description="Raw verification token from email link."),
    db: Session = Depends(get_db),
):
    rec = db.query(EmailVerification).filter(EmailVerification.token_hash == sha256(token)).first()
    if not rec:
        raise HTTPException(status_code=400, detail="Invalid verification token.")
    if rec.consumed_at is not None:
        return VerifyResponse(verified=True, message="Email already verified.")
    if ensure_aware(rec.expires_at) < now_utc():
        raise HTTPException(status_code=400, detail="Verification token has expired.")
    user = db.query(User).filter(User.id == rec.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="User not found for this token.")

    user.email_verified_at = now_utc()
    user.is_active = True  # optional but common
    rec.consumed_at = now_utc()
    db.commit()
    return VerifyResponse(verified=True, message="Email successfully verified.")

@router.post("/login", response_model=TokenPair)
def login(body: LoginBody, request: Request, db: Session = Depends(get_db)):
    email = body.email.lower().strip()
    user = db.query(User).filter(User.email==email).first()
    if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    if not user.is_active:
        raise HTTPException(403, "Email not verified")

    # pick default account (owner of any account, else first membership)
    mem = db.query(Membership).filter(Membership.user_id==user.id).first()
    if not mem:
        raise HTTPException(403, "No account membership")
    return issue_tokens(db, user, mem.account_id,
                        user_agent=request.headers.get("user-agent", ""),
                        ip=request.client.host if request.client else "")

@router.post("/refresh", response_model=TokenPair)
def refresh_token(request: Request, refresh_token: str, db: Session = Depends(get_db)):
    # refresh_token passed as form field or query; alternatively read from cookie
    try:
        payload = decode_jwt(refresh_token)
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid refresh token")
    jti = payload.get("jti")
    sub = payload.get("sub")
    aid = payload.get("aid")
    if not jti or not sub or not aid:
        raise HTTPException(401, "Invalid refresh token")

    # verify stored hash exists and not revoked/expired
    rt = db.query(RefreshToken).filter(RefreshToken.jti==jti, RefreshToken.token_hash==sha256(refresh_token)).first()
    if not rt or rt.revoked_at is not None or ensure_aware(rt.expires_at) < now_utc():
        raise HTTPException(401, "Refresh token invalid/revoked")

    # rotate: revoke old, create new
    rt.revoked_at = now_utc()
    user = db.get(User, UUID(sub))
    if not user or not user.is_active:
        raise HTTPException(401, "Invalid user")
    db.commit()

    return issue_tokens(db, user, UUID(aid),
                        user_agent=request.headers.get("user-agent", ""),
                        ip=request.client.host if request.client else "")

@router.post("/logout")
def logout(refresh_token: str, db: Session = Depends(get_db)):
    try:
        payload = decode_jwt(refresh_token)
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid refresh token")
    jti = payload.get("jti")
    rt = db.query(RefreshToken).filter(RefreshToken.jti==jti, RefreshToken.token_hash==sha256(refresh_token)).first()
    if rt and not rt.revoked_at:
        rt.revoked_at = now_utc()
        db.commit()
    return {"ok": True}



@router.get(
    "/me",
    response_model=Me,
    summary="Return the current authenticated user",
    description="""
Returns the profile of the currently logged-in user **and their account memberships**.

- Requires a valid **access token** in the `Authorization: Bearer <token>` header.
- If the token is missing, invalid, expired, or belongs to an inactive/unverified user, you'll get `401` or `403`.
- Response includes user fields plus a list of memberships (`account_id`, `role`, `account_name`).
"""
)
def me(user = Depends(current_user), db: Session = Depends(get_db)):
    # Query memberships joined with account for display name
    rows = (
        db.query(Membership, Account)
        .join(Account, Account.id == Membership.account_id)
        .filter(Membership.user_id == user.id)
        .all()
    )

    # Build DTOs explicitly (don't return ORM rows)
    memberships = [
        MembershipOut(
            account_id=acc.id,
            role=RoleEnum(m.role.name) if hasattr(m.role, "name") else RoleEnum(m.role),
            account_name=acc.name,
        )
        for (m, acc) in rows
    ]

    # Determine a default account to show subscription for: prefer the first membership if present
    account_id = memberships[0].account_id if memberships else None

    # Fetch subscription record for that account (if any) and follow same defaults as /accounts/{account_id}/subscriptions
    plan = None
    status = None
    current_period_end = None
    if account_id:
        from app.models.subscription import Subscription
        rec = db.query(Subscription).filter(Subscription.account_id == account_id).first()
        if not rec:
            # default to FREE
            plan = "FREE"
            status = "active"
            current_period_end = None
        else:
            plan = rec.plan
            # prefer raw_stripe_status for canonicalization if present, else fall back to stored status
            raw = getattr(rec, 'raw_stripe_status', None)
            status = canonicalize_status(raw or rec.status)
            current_period_end = ensure_aware(rec.current_period_end)

    # Compute is_subscribed: True iff plan == 'PRO' AND status == 'active' AND current_period_end not passed
    from app.core.security import now_utc
    is_subscribed = False
    # normalize plan casing and compare canonical status
    plan_key = plan.upper() if isinstance(plan, str) else None
    if plan_key == "PRO" and status == "active":
        # If current_period_end is None treat as active indefinite; otherwise ensure it's in the future
        if current_period_end is None:
            is_subscribed = True
        else:
            try:
                is_subscribed = current_period_end > now_utc()
            except Exception:
                is_subscribed = False

    # Return Me DTO with memberships and subscription flag
    return Me(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        is_active=user.is_active,
        memberships=memberships,
        is_subscribed=is_subscribed,
    )



# ---- Google (skeleton; wire later) ----

@router.get("/google/start", response_model=GoogleStartOut)
def google_start():
    if not settings.google_client_id:
        raise HTTPException(400, "Google OAuth not configured")
    # lazy import
    try:
        from authlib.integrations.requests_client import OAuth2Session  # noqa: F401
    except ImportError:
        raise HTTPException(500, "Install 'authlib' and 'requests' to use Google OAuth")

    scope = "openid email profile"
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": scope,
        "access_type": "offline",
        "prompt": "consent",
    }
    from urllib.parse import urlencode
    base = "https://accounts.google.com/o/oauth2/v2/auth"
    return {"auth_url": f"{base}?{urlencode(params)}"}

@router.post(
    "/google/callback",
    response_model=TokenPair,
    summary="Google OAuth callback → sign-in/sign-up + optional invite consumption",
    description="""
Exchanges a Google OAuth **authorization code** for tokens, fetches userinfo, and signs the user in.

**Behavior:**
- If an **invite** is provided and valid:
  - The Google account's email **must match** the invitation email, otherwise `400`.
  - The user is added to the invited account with the invited role, and the invite is marked accepted.
- If **no invite**:
  - If a user with this email **already exists**:
    - If the user has **no** `google_sub`, it is linked to this Google account.
    - If already linked, we reuse it (no overwrite of names).
    - The user is activated if needed.
  - If no user exists, we **create** one and **create a personal workspace** (OWNER).
- Returns a standard **TokenPair** (access + refresh).

**Notes:**
- The `code` may arrive URL-encoded; we safely decode it.
- Common OAuth errors (`invalid_grant`, `redirect_uri_mismatch`) are returned as `400` with a useful message.
""",
)
def google_callback(
    request: Request,
    code: str = Query(..., description="Authorization code returned by Google"),
    invite: str | None = Query(None, description="Optional invitation token"),
    db: Session = Depends(get_db),
):
    # 1) Decode code once to handle double-encoded cases (e.g., %252F → %2F)
    code = unquote(code)

    # 2) Exchange code for tokens
    try:
        sess = OAuth2Session(
            settings.google_client_id,
            settings.google_client_secret,
            scope="openid email profile",
            redirect_uri=settings.google_redirect_uri,
        )
        token = sess.fetch_token(
            "https://oauth2.googleapis.com/token",
            code=code,
            grant_type="authorization_code",
            # Explicitly pass these to avoid env misreads by the library:
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            redirect_uri=settings.google_redirect_uri,
        )
    except Exception as e:
        # Authlib raises OAuthError with .error and .description; keep it simple but helpful
        msg = str(e)
        if "invalid_grant" in msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or already-used authorization code. Start login again."
            )
        if "redirect_uri_mismatch" in msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Redirect URI mismatch. Ensure GOOGLE_REDIRECT_URI matches Google Console exactly."
            )
        raise HTTPException(status_code=400, detail=f"OAuth error: {msg}")

    # 3) Fetch userinfo from Google
    try:
        userinfo = sess.get("https://openidconnect.googleapis.com/v1/userinfo").json()
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to fetch Google profile.")

    email = str(userinfo.get("email", "")).lower().strip()
    sub = userinfo.get("sub")
    verified = bool(userinfo.get("email_verified", False))

    if not email or not sub:
        raise HTTPException(status_code=400, detail="Google profile missing email or subject.")
    if not verified:
        raise HTTPException(status_code=400, detail="Google account email is not verified.")

    # 4) If invite is supplied, consume/validate it (email must match)
    inv = None
    if invite:
        inv = _consume_invite(db, invite)  # must return Invitation or raise
        if inv.email.lower().strip() != email:
            raise HTTPException(status_code=400, detail="Use the Google account matching the invitation email.")

    # 5) Find or create user; link google_sub if needed
    user = db.query(User).filter(User.email == email).first()
    if not user:
        fn, ln = names_from_google_userinfo(userinfo, email)
        user = User(
            email=email,
            google_sub=sub,
            is_active=True,
            first_name=fn,
            last_name=ln,
        )
        db.add(user)
        db.flush()
    else:
        # If the email exists but is linked to a different Google sub, block to avoid hijack
        if user.google_sub and user.google_sub != sub:
            raise HTTPException(
                status_code=400,
                detail="This email is already linked to a different Google account."
            )
        # Link Google if not yet linked
        if not user.google_sub:
            user.google_sub = sub
        # Backfill names if missing (don't overwrite existing names)
        if not (user.first_name and user.last_name):
            fn, ln = names_from_google_userinfo(userinfo, email)
            user.first_name = user.first_name or fn
            user.last_name = user.last_name or ln
        # Activate if needed
        if not user.is_active:
            user.is_active = True
    if verified and not user.email_verified_at:
        user.email_verified_at = now_utc()       
    db.commit()

    # 6) Membership: invited vs default workspace
    if inv:
        exists = (
            db.query(Membership)
            .filter(Membership.account_id == inv.account_id, Membership.user_id == user.id)
            .first()
        )
        if not exists:
            db.add(Membership(account_id=inv.account_id, user_id=user.id, role=inv.role))
        inv.accepted_at = now_utc()
        if inv.manage_schema_ids:
            mem = db.query(Membership).filter(
                Membership.account_id == inv.account_id,
                Membership.user_id == user.id
            ).first()
        if mem:
            mem.manage_schema_ids = inv.manage_schema_ids

        db.commit()
        account_id = inv.account_id
    else:
        mem = db.query(Membership).filter(Membership.user_id == user.id).first()
        if not mem:
            name = _unique_account_name(db, email, user.first_name, user.last_name)
            account = Account(name=name, owner_user_id=user.id)
            db.add(account); db.flush()
            db.add(Membership(account_id=account.id, user_id=user.id, role=Role.OWNER))
            db.commit()
            account_id = account.id
        else:
            account_id = mem.account_id

    # 7) Issue tokens and return
    return issue_tokens(
        db, user, account_id,
        user_agent=request.headers.get("user-agent", ""),
        ip=request.client.host if request.client else ""
    )

# ---------- PASSWORD: REQUEST RESET ----------
@router.post(
    "/password/forgot",
    response_model=MessageResponse,
    summary="Send password reset email",
    description="""
Sends a password reset email with a link containing a reset token.

- Always returns a generic success message to avoid user enumeration.
- Works for both email+password users and Google-only users (they can set a password for the first time).
"""
)
def password_forgot(body: PasswordForgotBody, db: Session = Depends(get_db)):
    email = body.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()

    # Always return generic success
    if not user:
        return MessageResponse(message="If an account exists, a reset email has been sent.")

    try:
        issue_password_reset(db, user.id, email, user.first_name)
        db.commit()
    except Exception:
        db.rollback()
        # Still generic to avoid leaking state
        return MessageResponse(message="If an account exists, a reset email has been sent.")

    return MessageResponse(message="If an account exists, a reset email has been sent.")


# ---------- PASSWORD: PERFORM RESET ----------
@router.post(
    "/password/reset",
    response_model=MessageResponse,
    summary="Reset password using token",
    description="""
Resets the user's password using the token from the email link.

**Behavior:**
- Validates token (exists, not expired, not used).
- Sets/updates the user's password (works for Google-only users too).
- Revokes all existing refresh tokens for the user (forces re-login on other sessions).
"""
)
def password_reset(body: PasswordResetBody, db: Session = Depends(get_db)):
    token_h = sha256(body.token)
    rec = db.query(PasswordReset).filter(PasswordReset.token_hash == token_h).first()
    if not rec:
        raise HTTPException(status_code=400, detail="Invalid reset token.")
    if rec.consumed_at is not None:
        raise HTTPException(status_code=400, detail="Reset token already used.")
    if rec.expires_at < now_utc():
        raise HTTPException(status_code=400, detail="Reset token has expired.")

    user = db.query(User).filter(User.id == rec.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="User not found for this token.")

    # Set/overwrite password (supports Google-only users who had no password)
    user.password_hash = hash_password(body.new_password)

    # Optional hardening: revoke all refresh tokens for this user
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id,
        RefreshToken.revoked_at.is_(None)
    ).update({RefreshToken.revoked_at: now_utc()})

    rec.consumed_at = now_utc()
    db.commit()

    return MessageResponse(message="Password has been reset. Please log in with your new password.")
