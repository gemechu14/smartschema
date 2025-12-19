from datetime import timedelta, datetime
from typing import Tuple, List, Set
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status

from app.core.config import settings
from app.core.security import random_token, sha256, now_utc
from app.services.mailer import send_email
from app.models.survey import Survey, SurveyInvite, SurveyResponse, SurveyStatus


def generate_survey_token() -> Tuple[str, str]:
    """
    Generate a secure survey token.
    
    Returns:
        Tuple of (raw_token, token_hash)
    """
    raw = random_token(32)
    hashed = sha256(raw)
    return raw, hashed


def create_survey_invites_batch(
    db: Session,
    survey_id: UUID,
    emails: List[str],
    expires_at: datetime
) -> List[Tuple[str, SurveyInvite]]:
    """
    Batch create survey invites.
    
    Args:
        db: Database session
        survey_id: Survey UUID
        emails: List of email addresses
        expires_at: Expiration datetime
    
    Returns:
        List of tuples (raw_token, invite_record)
    """
    invites = []
    
    for email in emails:
        raw_token, token_hash = generate_survey_token()
        
        invite = SurveyInvite(
            survey_id=survey_id,
            email=email.lower().strip(),
            token_hash=token_hash,
            expires_at=expires_at,
            created_at=now_utc()
        )
        
        db.add(invite)
        invites.append((raw_token, invite))
    
    return invites


def send_survey_invitation_email(
    email: str,
    raw_token: str,
    survey_name: str,
    survey_description: str,
    expires_at: datetime
):
    """
    Send a formal survey invitation email.
    
    Args:
        email: Recipient email address
        raw_token: Raw survey token (not hashed)
        survey_name: Survey name
        survey_description: Survey description
        expires_at: Survey expiration date
    """
    # Use fragment (#) instead of query param for security - fragments are not sent to server
    # Use fragment (#) instead of query param for security - fragments are not sent to server
    # Frontend will extract token from fragment and send in request body
    link = f"{settings.app_base_url}/surveys/submit#{raw_token}"
    
    # Format expiry date
    expiry_str = expires_at.strftime("%B %d, %Y at %I:%M %p UTC") if expires_at else "No expiration"
    
    # Create description snippet
    desc_snippet = f"<p>{survey_description}</p>" if survey_description else ""
    # greeting = "Hello,"
    # greeting = "Hello,"+ `email.split("@")[0]`
    greeting = "Hello " + email.split("@")[0] + ","



    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Survey Invitation - {survey_name}</title>
    <style>
        body {{ font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f6f8fb; margin: 0; padding: 0; color: #333; }}
        .container {{ max-width: 600px; margin: 40px auto; background-color: #fff; border-radius: 12px; box-shadow: 0 4px 8px rgba(0,0,0,0.05); overflow: hidden; }}
        .header {{ background-color: #0f172a; color: #fff; text-align: center; padding: 28px 24px; }}
        .content {{ padding: 28px 32px; line-height: 1.6; }}
        .btn {{ display:inline-block; background:#0f172a; color:#ffffff !important; -webkit-text-size-adjust:none; padding:12px 20px; border-radius:8px; text-decoration:none }}
        .footer {{ text-align: center; color: #999; font-size: 12px; padding: 16px 0; }}
        h1 {{ margin: 0; font-size: 22px; }}
        h3 {{ margin-top: 0; }}
        .info-box {{ background-color: #f0f4f8; padding: 12px; border-radius: 6px; margin: 16px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Survey Invitation</h1>
        </div>
        <div class="content">
             <p><strong>{greeting}</strong></p>
            <h3>{survey_name}</h3>
            {desc_snippet}
            <p>You have been invited to participate in this survey. Your response is valuable and will help us gather important insights.</p>
            
            <div class="info-box">
                <strong>Survey Details:</strong><br>
                <strong>Name:</strong> {survey_name}<br>
                <strong>Expires:</strong> {expiry_str}
            </div>
            
            <p style="text-align:center; margin: 24px 0;">
                <a class="btn" href="{link}" style="color:#ffffff !important; text-decoration:none;">
                    Take Survey
                </a>
            </p>
            
            <p style="font-size: 13px; color: #666;">
                If the button doesn't work, copy and paste this URL into your browser:<br>
                <a href="{link}" style="word-break: break-all;">{link}</a>
            </p>
            
            <p style="font-size: 13px; color: #666; margin-top: 24px;">
                This is a secure invitation link. Do not share this link with others as it is uniquely assigned to you.
            </p>
        </div>
        <div class="footer">
            &copy; {datetime.utcnow().year} SmartSchema. All rights reserved.
        </div>
    </div>
</body>
</html>
'''
    
    send_email(
        to_email=email,
        subject=f"Survey Invitation: {survey_name}",
        html=html
    )


def validate_survey_token(
    db: Session,
    token: str
) -> Tuple[Survey, SurveyInvite]:
    """
    Validate a survey token and return the survey and invite.
    
    Raises:
        HTTPException: If token is invalid, expired, revoked, or already submitted
    
    Returns:
        Tuple of (Survey, SurveyInvite)
    """
    if not token or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token is required"
        )
    
    # Clean token (remove any whitespace or URL encoding artifacts)
    token = token.strip()
    
    # Hash the token
    token_hash = sha256(token)
    
    # Find invite by token hash
    invite = db.query(SurveyInvite).filter(
        SurveyInvite.token_hash == token_hash
    ).first()
    
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid survey token"
        )
    
    # Check if revoked
    if invite.revoked_at:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This survey invitation has been revoked"
        )
    
    # Check if expired
    if now_utc() > invite.expires_at:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This survey invitation has expired"
        )
    
    # Check if already submitted
    if invite.submitted_at:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You have already submitted this survey"
        )
    
    # Get survey
    survey = db.query(Survey).filter(
        Survey.id == invite.survey_id,
        Survey.deleted_at == None
    ).first()
    
    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found"
        )
    
    # Check if survey is closed
    if survey.status != SurveyStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This survey is no longer accepting responses"
        )
    
    # Check survey expiry
    if survey.expires_at and now_utc() > survey.expires_at:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This survey has expired"
        )
    
    return survey, invite


def get_new_emails(
    db: Session,
    survey_id: UUID,
    new_email_list: List[str]
) -> List[str]:
    """
    Filter out emails that already have invites for this survey.
    
    Args:
        db: Database session
        survey_id: Survey UUID
        new_email_list: List of email addresses to check
    
    Returns:
        List of email addresses that don't have existing invites
    """
    # Normalize emails
    normalized = [email.lower().strip() for email in new_email_list]
    
    # Get existing invites
    existing = db.query(SurveyInvite.email).filter(
        SurveyInvite.survey_id == survey_id,
        SurveyInvite.email.in_(normalized)
    ).all()
    
    existing_set: Set[str] = {email for (email,) in existing}
    
    # Return only new emails
    return [email for email in normalized if email not in existing_set]


def get_survey_stats(db: Session, survey_id: UUID) -> dict:
    """
    Get statistics for a survey.
    
    Args:
        db: Database session
        survey_id: Survey UUID
    
    Returns:
        Dictionary with total_invites, opened_count, submitted_count
    """
    invites = db.query(SurveyInvite).filter(
        SurveyInvite.survey_id == survey_id
    ).all()
    
    total = len(invites)
    opened = sum(1 for inv in invites if inv.opened_at)
    submitted = sum(1 for inv in invites if inv.submitted_at)
    
    return {
        "total_invites": total,
        "opened_count": opened,
        "submitted_count": submitted
    }


def batch_process_invites(
    db: Session,
    survey_id: UUID,
    emails: List[str],
    expires_at: datetime,
    batch_size: int = 1000
) -> List[Tuple[str, SurveyInvite]]:
    """
    Process invites in batches for large email lists.
    
    Args:
        db: Database session
        survey_id: Survey UUID
        emails: List of email addresses
        expires_at: Expiration datetime
        batch_size: Number of invites per batch
    
    Returns:
        List of all created (raw_token, invite_record) tuples
    """
    all_invites = []
    
    for i in range(0, len(emails), batch_size):
        batch = emails[i:i + batch_size]
        batch_invites = create_survey_invites_batch(db, survey_id, batch, expires_at)
        all_invites.extend(batch_invites)
        
        # Commit each batch
        db.commit()
    
    return all_invites















