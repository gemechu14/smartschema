import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Optional
from app.core.config import settings

def send_email(to_email: str, subject: str, html: str, from_name: Optional[str] = None):
    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = formataddr((from_name or settings.mail_from_name, settings.mail_from))
    msg["To"] = to_email

    with smtplib.SMTP(settings.smtp_server, settings.smtp_port) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(mail_from, [to_email], msg.as_string())
