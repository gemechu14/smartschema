from pydantic import BaseModel
import os


from dotenv import load_dotenv
load_dotenv()
class Settings(BaseModel):
    database_url: str = os.getenv("DATABASE_URL", "")
    app_name: str = os.getenv("APP_NAME", "SmartSchema")

    jwt_secret: str = os.getenv("JWT_SECRET", "change-me")
    jwt_issuer: str = os.getenv("JWT_ISSUER", "locimapper-api")
    access_ttl_min: int = int(os.getenv("ACCESS_TOKEN_TTL_MIN", "15"))
    refresh_ttl_days: int = int(os.getenv("REFRESH_TOKEN_TTL_DAYS", "30"))

    smtp_server: str = os.getenv("SMTP_SERVER", "")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    mail_from: str = os.getenv("MAIL_FROM", "")
    mail_from_name: str = os.getenv("MAIL_FROM_NAME", "SmartSchema")

    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    google_redirect_uri: str = os.getenv("GOOGLE_REDIRECT_URI", "")

    app_base_url: str = os.getenv("APP_BASE_URL", "https://app.smartschema.io")
    invite_exp_days: int = int(os.getenv("INVITE_EXP_DAYS", "7"))
    email_verify_exp_hours: int = int(os.getenv("EMAIL_VERIFY_EXP_HOURS", "24"))
    # Cooldown in seconds before allowing another verification email to be resent for the same account
    email_verify_resend_cooldown_seconds: int = int(os.getenv("EMAIL_VERIFY_RESEND_COOLDOWN_S", "60"))
    # Password reset link expiry in hours (default 24 to match UX)
    password_reset_exp_hours: int = int(os.getenv("PASSWORD_RESET_EXP_HOURS", "24"))
    # Launch token TTL (seconds) for standalone import page tokens (default 5 minutes)
    launch_token_ttl_seconds: int = int(os.getenv("LAUNCH_TOKEN_TTL_SECONDS", "300"))
    
    # Survey settings
    survey_invite_exp_days: int = int(os.getenv("SURVEY_INVITE_EXP_DAYS", "14"))
    survey_batch_size: int = int(os.getenv("SURVEY_BATCH_SIZE", "1000"))

settings = Settings()
