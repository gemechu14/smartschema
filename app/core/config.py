from pydantic import BaseModel
import os


from dotenv import load_dotenv
load_dotenv()
class Settings(BaseModel):
    database_url: str = os.getenv("DATABASE_URL", "")
    app_name: str = os.getenv("APP_NAME", "Locimapper")

    jwt_secret: str = os.getenv("JWT_SECRET", "change-me")
    jwt_issuer: str = os.getenv("JWT_ISSUER", "locimapper-api")
    access_ttl_min: int = int(os.getenv("ACCESS_TOKEN_TTL_MIN", "15"))
    refresh_ttl_days: int = int(os.getenv("REFRESH_TOKEN_TTL_DAYS", "30"))

    smtp_server: str = os.getenv("SMTP_SERVER", "")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    mail_from: str = os.getenv("MAIL_FROM", "")
    mail_from_name: str = os.getenv("MAIL_FROM_NAME", "Locimapper")

    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    google_redirect_uri: str = os.getenv("GOOGLE_REDIRECT_URI", "")

    app_base_url: str = os.getenv("APP_BASE_URL", "http://3.141.190.135:8000")
    invite_exp_days: int = int(os.getenv("INVITE_EXP_DAYS", "7"))
    email_verify_exp_hours: int = int(os.getenv("EMAIL_VERIFY_EXP_HOURS", "24"))

settings = Settings()
