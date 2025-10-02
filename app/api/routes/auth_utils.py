# app/api/routes/auth_utils.py
from datetime import timedelta
from typing import Tuple
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import random_token, sha256, now_utc
from app.services.mailer import send_email
from app.models.verification import EmailVerification
from app.models.password_reset import PasswordReset

def issue_email_verification(db: Session, user_id, to_email: str, first_name: str | None) -> Tuple[str, EmailVerification]:
    """Create a fresh email verification token, store only its hash, and send the email."""
    raw = random_token(32)
    rec = EmailVerification(
        user_id=user_id,
        token_hash=sha256(raw),
        expires_at=now_utc() + timedelta(hours=settings.email_verify_exp_hours),
    )
    db.add(rec); db.flush()

    link = f"{settings.app_base_url}/auth/verify?token={raw}"
    name = first_name or to_email.split("@")[0].capitalize()
    html = f"""
      <p>Hi {name},</p>
      <p>Please verify your email to activate your account.</p>
      <p><a href="{link}">Verify email</a></p>
      <p>If the button doesn't work, copy and paste this URL:<br>{link}</p>
    """
    send_email(to_email=to_email, subject="Verify your email", html=html)
    return raw, rec


def clean_name(s: str | None) -> str | None:
    if not s:
        return None
    s = " ".join(s.strip().split())  # collapse spaces
    # Simple capitalization; keep existing casing if you prefer
    return s[:80]

def names_from_google_userinfo(userinfo: dict, email: str) -> tuple[str | None, str | None]:
    gn = clean_name(userinfo.get("given_name"))
    fn = clean_name(userinfo.get("family_name"))
    if gn or fn:
        return gn, fn
    full = clean_name(userinfo.get("name"))
    if full:
        parts = [p for p in full.replace("_", " ").replace(".", " ").split() if p]
        if len(parts) >= 2:
            return parts[0], " ".join(parts[1:])
        return parts[0], None
    # Fallback last resort: email local-part
    local = email.split("@", 1)[0]
    pieces = [p for p in local.replace("_", " ").replace(".", " ").split() if p]
    if len(pieces) >= 2:
        return pieces[0].capitalize(), " ".join(p.capitalize() for p in pieces[1:])
    return local.capitalize(), None

def issue_password_reset(db: Session, user_id, to_email: str, first_name: str | None):
    """Create a reset token (store only hash), send email with reset link."""
    raw = random_token(32)
    rec = PasswordReset(
        user_id=user_id,
        token_hash=sha256(raw),
        expires_at=now_utc() + timedelta(hours=2),  # reset links valid for 2h
    )
    db.add(rec); db.flush()

    link = f"{settings.app_base_url}/auth/password/reset?token={raw}"
    name = first_name or to_email.split("@")[0].capitalize()
    html = f"""
      <p>Hi {name},</p>
      <p>We received a request to reset your password.</p>
      <p><a href="{link}">Reset your password</a></p>
      <p>If the button doesn't work, copy and paste:<br>{link}</p>
      <p>If you didn't request this, you can safely ignore this email.</p>
    """
    send_email(to_email=to_email, subject="Reset your password", html=html)
    return raw, rec
