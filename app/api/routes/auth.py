from datetime import timedelta
from uuid import uuid4, UUID
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from authlib.integrations.requests_client import OAuth2Session

from app.api.deps import get_db
from app.api.deps_auth import current_user
from app.core.config import settings
from app.core.security import (
    hash_password, verify_password, make_access_token, make_refresh_token,
    sha256, parse_name_from_email, now_utc, decode_jwt
)
from app.models.auth_models import User, Account, Membership, Role, Invitation, RefreshToken
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

@router.post("/signup", response_model=TokenPair)
def signup(body: SignupBody, request: Request, db: Session = Depends(get_db)):
    email = body.email.lower().strip()

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    try:
        pw_hash = hash_password(body.password)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid password format")

    # Use names provided by frontend
    first_name = clean_name(body.first_name) or ""
    last_name  = clean_name(body.last_name) or ""

    user = User(
        email=email,
        password_hash=pw_hash,
        is_active=False,   # or True if you don’t require email verification
        first_name=first_name,
        last_name=last_name,
    )
    db.add(user); db.flush()

    account_id = None
    if body.invite:
        inv = _consume_invite(db, body.invite)
        if inv.email.lower().strip() != email:
            raise HTTPException(status_code=400, detail="Invite email mismatch")
        db.add(Membership(account_id=inv.account_id, user_id=user.id, role=inv.role))
        inv.accepted_at = now_utc()
        account_id = inv.account_id
        db.commit()

    if account_id is None:
        # auto-generate account name; owner membership
        name = _unique_account_name(db, email, first_name, last_name)
        account = Account(name=name, owner_user_id=user.id)
        db.add(account); db.flush()
        db.add(Membership(account_id=account.id, user_id=user.id, role=Role.OWNER))
        account_id = account.id
        db.commit()

    return issue_tokens(
        db, user, account_id,
        user_agent=request.headers.get("user-agent", ""),
        ip=request.client.host if request.client else ""
    )

@router.get("/verify-email")
def verify_email(token: str, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], issuer=settings.jwt_issuer)
        if payload.get("type") != "verify_email":
            raise HTTPException(400, "Bad token")
        user_id = payload.get("sub")
    except jwt.PyJWTError:
        raise HTTPException(400, "Invalid or expired token")
    user = db.get(User, UUID(user_id))
    if not user:
        raise HTTPException(400, "User not found")
    if not user.is_active:
        user.is_active = True
        user.email_verified_at = now_utc()
        db.commit()
    return {"ok": True}

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
    if not rt or rt.revoked_at is not None or rt.expires_at < now_utc():
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

@router.get("/me", response_model=Me)
def me(user = Depends(current_user)):
    return user

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

@router.post("/google/callback", response_model=TokenPair)
def google_callback(
    code: str,
    request: Request,
    invite: str | None = None,
    db: Session = Depends(get_db),
):
    # ... exchange code for token & userinfo
    sess = OAuth2Session(settings.google_client_id, settings.google_client_secret,
                         scope="openid email profile", redirect_uri=settings.google_redirect_uri)
    token = sess.fetch_token("https://oauth2.googleapis.com/token", code=code)
    userinfo = sess.get("https://openidconnect.googleapis.com/v1/userinfo").json()

    email = str(userinfo.get("email", "")).lower()
    sub = userinfo.get("sub")
    verified = bool(userinfo.get("email_verified", False))
    if not email or not sub:
        raise HTTPException(400, "Google profile missing email/sub")
    if not verified:
        raise HTTPException(400, "Google account email is not verified")

    inv = _consume_invite(db, invite) if invite else None
    if inv and inv.email.lower().strip() != email:
        raise HTTPException(400, "Please use the Google account matching the invitation email.")

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
        db.add(user); db.flush()
    else:
        if not user.google_sub:
            user.google_sub = sub
        # Only fill missing fields; do not overwrite user-entered names
        if not (user.first_name and user.last_name):
            fn, ln = names_from_google_userinfo(userinfo, email)
            user.first_name = user.first_name or fn
            user.last_name  = user.last_name  or ln
        if not user.is_active:
            user.is_active = True
    db.commit()

    if inv:
        exists = (
            db.query(Membership)
            .filter(Membership.account_id == inv.account_id, Membership.user_id == user.id)
            .first()
        )
        if not exists:
            db.add(Membership(account_id=inv.account_id, user_id=user.id, role=inv.role))
        inv.accepted_at = now_utc()
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

    return issue_tokens(
        db, user, account_id,
        user_agent=request.headers.get("user-agent", ""),
        ip=request.client.host if request.client else ""
    )
