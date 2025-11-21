from fastapi import APIRouter, HTTPException
from app.schemas.auth import ContactBody, MessageResponse
from app.services.mailer import send_email
from app.core.config import settings

router = APIRouter()

@router.post("/contact", response_model=MessageResponse, summary="Public contact form -> email to admin")
def contact_us(body: ContactBody):
    """Public contact endpoint. No authentication required.

    Sends a formatted email to admin@smartschema.io with the provided fields.
    """
    admin_email = "admin@smartschema.io"
    subject = f"New contact form submission from {body.full_name}"
    # Build a simple HTML body
    html = f"""<!doctype html>
    <html>
      <body>
        <h2>New contact form submission</h2>
        <p><strong>Full name:</strong> {body.full_name}</p>
        <p><strong>Work email:</strong> {body.work_email}</p>
        <p><strong>Company:</strong> {body.company or ''}</p>
        <p><strong>Team size:</strong> {body.team_size or ''}</p>
        <p><strong>Use case:</strong> {body.use_case or ''}</p>
        <hr/>
        <p><strong>Additional information:</strong></p>
        <pre style="white-space: pre-wrap;">{body.additional_info or ''}</pre>
      </body>
    </html>
    """
    try:
        send_email(admin_email, subject, html, from_name=settings.mail_from_name)
    except Exception as e:
        # don't leak internals; log could be added here
        raise HTTPException(status_code=500, detail="Failed to send message")
    return MessageResponse(ok=True, message="Message sent")
