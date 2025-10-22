from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
import hashlib, hmac, os, re, base64, secrets
import jwt
from passlib.context import CryptContext
from app.core.config import settings
from datetime import timezone as _tz, datetime as _dt

pwd_ctx = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
ALGO = "HS256"

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

def ensure_aware(dt: _dt) -> _dt:
    """Return a timezone-aware UTC datetime. If naive, assume UTC."""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=_tz.utc)

def hash_password(p: str) -> str:
    # No length truncation required
    return pwd_ctx.hash(p)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)

def now_utc():
    return datetime.now(timezone.utc)

def make_access_token(sub: str, account_id: str, role: str) -> str:
    payload = {
        "iss": settings.jwt_issuer,
        "sub": sub,
        "aid": account_id,
        "role": role,
        "iat": int(now_utc().timestamp()),
        "exp": int((now_utc() + timedelta(minutes=settings.access_ttl_min)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGO)


def make_launch_token(integration_id: str, credential_id: str, account_id: str, ttl_seconds: int = 300) -> str:
    """Create a short-lived JWT for launching the standalone import page.

    Contains minimal claims: integration id, credential id, account id, issued at and expiry.
    """
    payload = {
        "iss": settings.jwt_issuer,
        "int_id": str(integration_id),
        "cred_id": str(credential_id),
        "aid": str(account_id),
        "iat": int(now_utc().timestamp()),
        "exp": int((now_utc() + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGO)

def make_refresh_token(sub: str, account_id: str, jti: str) -> str:
    payload = {
        "iss": settings.jwt_issuer,
        "sub": sub,
        "aid": account_id,
        "jti": jti,
        "iat": int(now_utc().timestamp()),
        "exp": int((now_utc() + timedelta(days=settings.refresh_ttl_days)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGO)

def decode_jwt(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[ALGO], issuer=settings.jwt_issuer)

def random_token(n_bytes: int = 32) -> str:
    return base64.urlsafe_b64encode(os.urandom(n_bytes)).decode("utf-8").rstrip("=")

def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def parse_name_from_email(email: str) -> Tuple[Optional[str], Optional[str]]:
    # very simple heuristic: split local-part on . _ or -
    local = email.split("@")[0]
    parts = re.split(r"[._\-]+", local)
    if len(parts) >= 2:
        fn = parts[0].capitalize()
        ln = parts[-1].capitalize()
        return fn, ln
    return (local.capitalize(), None)
