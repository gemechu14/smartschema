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
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Welcome to SmartSchema</title>
    <style>
        body {{ font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f6f8fb; margin: 0; padding: 0; color: #333; }}
        .container {{ max-width: 600px; margin: 40px auto; background-color: #fff; border-radius: 12px; box-shadow: 0 4px 8px rgba(0,0,0,0.05); overflow: hidden; }}
        .header {{ background-color: #0f172a; color: #fff; text-align: center; padding: 28px 24px; }}
        .content {{ padding: 28px 32px; line-height: 1.6; }}
        .btn {{ display:inline-block; background:#0f172a; color:#ffffff !important; -webkit-text-size-adjust:none; padding:12px 20px; border-radius:8px; text-decoration:none }}
        .footer {{ text-align: center; color: #999; font-size: 12px; padding: 16px 0; }}
        h1 {{ margin: 0; font-size: 22px; }}
        h3 {{ margin-top: 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Welcome to SmartSchema</h1>
        </div>
        <div class="content">
            <h3>Hello {name},</h3>
            <p>Welcome to <strong>SmartSchema</strong> — your trusted platform for seamless data mapping and validation. To complete your signup, please verify your email address below:</p>
            <p style="text-align:left;"><a class="btn" href="{link}" style="color:#ffffff !important; text-decoration:none;">Verify My Email</a></p>
            <p>If the button doesn't work, copy and paste this URL into your browser:<br><a href="{link}">{link}</a></p>
            <p>If you didn’t sign up for SmartSchema, simply ignore this message.</p>
            <p>Cheers,<br>The SmartSchema Team</p>
        </div>
        <div class="footer">
            &copy; {__import__('datetime').datetime.utcnow().year} SmartSchema. All rights reserved.
        </div>
    </div>
</body>
</html>
'''
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
        expires_at=now_utc() + timedelta(hours=settings.password_reset_exp_hours),
    )
    db.add(rec); db.flush()

    link = f"{settings.app_base_url}/auth/password/reset?token={raw}"
    name = first_name or to_email.split("@")[0].capitalize()
    hours = settings.password_reset_exp_hours
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Password Changed Successfully - SmartSchema</title>
    <style>
        body {{ font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f6f8fb; margin: 0; padding: 0; color: #333; }}
        .container {{ max-width: 600px; margin: 40px auto; background-color: #fff; border-radius: 12px; box-shadow: 0 4px 8px rgba(0,0,0,0.05); overflow: hidden; }}
        .header {{ background-color: #0f172a; color: #fff; text-align: center; padding: 24px; }}
        .content {{ padding: 32px; line-height: 1.6; }}
        .btn {{ display:inline-block; background:#0f172a; color:#ffffff !important; -webkit-text-size-adjust:none; padding:12px 20px; border-radius:8px; text-decoration:none }}
        .footer {{ text-align: center; color: #999; font-size: 12px; padding: 16px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>SmartSchema</h2>
        </div>
        <div class="content">
            <h3>Reset Your Password</h3>
            <p>Hello {name},</p>
            <p>We received a request to reset your password for your <strong>SmartSchema</strong> account. You can set a new password by clicking the button below:</p>
            <p><a class="btn" href="{link}" style="color:#ffffff !important; text-decoration:none; display:inline-block;">Reset Password</a></p>
            <p>This link will expire in <strong>{hours} hours</strong>. If you didn’t request a password reset, you can safely ignore this message.</p>
            <p>Stay secure,<br>The SmartSchema Team</p>
        </div>
        <div class="footer">
            &copy; {__import__('datetime').datetime.utcnow().year} SmartSchema. All rights reserved.
        </div>
    </div>
</body>
</html>
'''
    send_email(to_email=to_email, subject="Reset your password", html=html)
    return raw, rec
