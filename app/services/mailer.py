# import smtplib
# from email.mime.text import MIMEText
# from email.utils import formataddr
# from typing import Optional
# from app.core.config import settings

# def send_email(to_email: str, subject: str, html: str, from_name: Optional[str] = None):
#     """
#     Send an email via SMTP.
    
#     Args:
#         to_email: Recipient email address
#         subject: Email subject
#         html: HTML email body
#         from_name: Optional sender name
        
#     Raises:
#         smtplib.SMTPException: If email sending fails
#         ConnectionError: If SMTP connection fails
#     """
#     msg = MIMEText(html, "html", "utf-8")
#     msg["Subject"] = subject
#     msg["From"] = formataddr((from_name or settings.mail_from_name, settings.mail_from))
#     msg["To"] = to_email

#     try:
#         # Create SMTP connection with timeout (30 seconds)
#         server = smtplib.SMTP(settings.smtp_server, settings.smtp_port, timeout=30)
#         try:
#             server.starttls()
#             server.login(settings.smtp_user, settings.smtp_password)
#             server.sendmail(settings.mail_from, [to_email], msg.as_string())
#         finally:
#             server.quit()
#     except smtplib.SMTPException as e:
#         raise Exception(f"SMTP error sending email to {to_email}: {str(e)}")
#     except (ConnectionError, OSError, TimeoutError) as e:
#         raise Exception(f"Connection error sending email to {to_email}: {str(e)}")
#     except Exception as e:
#         raise Exception(f"Unexpected error sending email to {to_email}: {str(e)}")


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

    # Add timeout to prevent indefinite hangs
    with smtplib.SMTP(settings.smtp_server, settings.smtp_port, timeout=30) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.mail_from, [to_email], msg.as_string())