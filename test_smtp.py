"""
SMTP Connection Test Script
Run this to diagnose email sending issues
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr
from dotenv import load_dotenv

load_dotenv()

SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
MAIL_FROM = os.getenv("MAIL_FROM")
MAIL_FROM_NAME = os.getenv("MAIL_FROM_NAME", "SmartSchema")

print("=" * 60)
print("SMTP CONNECTION TEST")
print("=" * 60)
print(f"\nSMTP Server: {SMTP_SERVER}")
print(f"SMTP Port: {SMTP_PORT}")
print(f"SMTP User: {SMTP_USER}")
print(f"Mail From: {MAIL_FROM}")
print(f"From Name: {MAIL_FROM_NAME}")
print(f"Password: {'*' * len(SMTP_PASSWORD) if SMTP_PASSWORD else 'NOT SET'}")

test_email = input("\nEnter test email address to send to: ").strip()

if not test_email:
    print("No email provided. Exiting.")
    exit(1)

print(f"\nAttempting to send test email to: {test_email}")
print("Please wait...\n")

try:
    # Create test message
    msg = MIMEText("<h1>Test Email</h1><p>If you receive this, SMTP is working correctly!</p>", "html", "utf-8")
    msg["Subject"] = "SMTP Test - SmartSchema"
    msg["From"] = formataddr((MAIL_FROM_NAME, MAIL_FROM))
    msg["To"] = test_email

    # Connect with timeout
    print(f"[1/4] Connecting to {SMTP_SERVER}:{SMTP_PORT}...")
    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30)
    print("✓ Connected successfully")

    # Start TLS
    print("[2/4] Starting TLS encryption...")
    server.starttls()
    print("✓ TLS started")

    # Login
    print("[3/4] Logging in...")
    server.login(SMTP_USER, SMTP_PASSWORD)
    print("✓ Login successful")

    # Send email
    print("[4/4] Sending email...")
    server.sendmail(MAIL_FROM, [test_email], msg.as_string())
    print("✓ Email sent successfully!")

    server.quit()

    print("\n" + "=" * 60)
    print("SUCCESS! SMTP is working correctly.")
    print("=" * 60)

except smtplib.SMTPAuthenticationError as e:
    print(f"\n✗ Authentication failed: {e}")
    print("\nPossible issues:")
    print("- Check SMTP_USER and SMTP_PASSWORD in .env file")
    print("- Gmail requires 'App Password', not regular password")
    print("- Go to: https://myaccount.google.com/apppasswords")

except smtplib.SMTPException as e:
    print(f"\n✗ SMTP error: {e}")
    print("\nPossible issues:")
    print("- SMTP server might be blocking your IP")
    print("- Check SMTP_SERVER and SMTP_PORT settings")

except (ConnectionError, OSError, TimeoutError) as e:
    print(f"\n✗ Connection error: {e}")
    print("\nPossible issues:")
    print("- Firewall blocking port 587")
    print("- Antivirus blocking SMTP")
    print("- Network/ISP blocking SMTP connections")
    print("- VPN interfering with connection")
    print("\nTroubleshooting steps:")
    print("1. Temporarily disable firewall/antivirus and test")
    print("2. Try on a different network (mobile hotspot)")
    print("3. Check if your ISP blocks port 587")
    print("4. Try port 465 (SSL) instead of 587 (TLS)")

except Exception as e:
    print(f"\n✗ Unexpected error: {e}")
    import traceback
    traceback.print_exc()

print("\n")









