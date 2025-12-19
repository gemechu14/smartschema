from typing import List, Optional
from uuid import UUID
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.api.deps import get_db
from app.api.deps_auth import require_role_for_account
from app.models.auth_models import Role
from app.models.survey import Survey, SurveyInvite, SurveyResponse, SurveyStatus
from app.models.schema_spec import SchemaSpecification
from app.schemas.survey import (
    SurveyCreateBody, SurveyUpdateBody, SurveyOut, SurveyDetailOut,
    SurveyCreateResponse, SurveyListResponse, SurveyCloseResponse,
    MessageResponse, SurveyInviteOut, SurveyOverviewResponse, SurveyOverviewOut,
    SurveyStatsResponse, SurveyStatsOut, SurveyResponseOut,
    SurveyResponseListResponse, SurveyResponseDetailResponse,
    transform_response_data_to_rows, SurveyRevokeInviteBody
)
from app.services.survey_service import (
    batch_process_invites, get_new_emails, get_survey_stats,
    send_survey_invitation_email
)
from app.core.config import settings
from app.core.security import now_utc


router = APIRouter(prefix="/accounts/{account_id}/surveys", tags=["surveys"])


def send_invites_background(invite_ids: List[UUID], tokens_map: dict, survey_name: str, survey_description: str):
    """Background task to send survey invitation emails."""
    from app.db.session import SessionLocal
    
    db = SessionLocal()
    try:
        for invite_id in invite_ids:
            raw_token = tokens_map.get(str(invite_id))
            if not raw_token:
                continue
                
            invite = db.query(SurveyInvite).filter(SurveyInvite.id == invite_id).first()
            if not invite:
                continue
                
            try:
                send_survey_invitation_email(
                    email=invite.email,
                    raw_token=raw_token,
                    survey_name=survey_name,
                    survey_description=survey_description or "",
                    expires_at=invite.expires_at
                )
                # Update sent_at after successful send
                invite.sent_at = now_utc()
                db.commit()
            except Exception as e:
                # Log error but continue with other emails
                # Note: Survey was created successfully, emails can be resent later
                error_msg = str(e)
                print(f"⚠️  Failed to send email to {invite.email}: {error_msg}")
                # Don't update sent_at if email failed
                db.rollback()
                # Continue with next email
    finally:
        db.close()


# ============ CREATE SURVEY ============

@router.post(
    "",
    response_model=SurveyCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a survey with invitations",
    description="""
Create a new survey and send invitations to specified email addresses.
Only **OWNER** or **ADMIN** can create surveys.

- Survey is created with ACTIVE status by default
- Invitations are sent via email in the background
- Each email can only be invited once per survey
- Emails are batched for efficiency (1000 per batch)
- Emails are optional - you can create a survey without invitations
"""
)
def create_survey(
    account_id: UUID,
    body: SurveyCreateBody,
    background_tasks: BackgroundTasks,
    tup=Depends(require_role_for_account({Role.OWNER, Role.ADMIN})),
    db: Session = Depends(get_db),
):
    user, _aid, _role = tup
    
    # Validate schema_id if provided
    if body.schema_id:
        schema_spec = db.query(SchemaSpecification).filter(
            SchemaSpecification.id == body.schema_id,
            SchemaSpecification.account_id == account_id,
            SchemaSpecification.deleted_at == None
        ).first()
        
        if not schema_spec:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Schema not found"
            )
    
    # Set default expiry if not provided
    expires_at = body.expires_at
    if not expires_at:
        expires_at = now_utc() + timedelta(days=settings.survey_invite_exp_days)
    
    # Create survey
    survey = Survey(
        account_id=account_id,
        schema_id=body.schema_id,
        name=body.name,
        description=body.description,
        status=SurveyStatus.ACTIVE,
        expires_at=expires_at,
        created_by_user_id=user.id,
        created_at=now_utc()
    )
    
    db.add(survey)
    db.commit()
    db.refresh(survey)
    
    # Batch process invites only if emails are provided
    invites_with_tokens = []
    if body.emails and len(body.emails) > 0:
        invite_expiry = expires_at or (now_utc() + timedelta(days=settings.survey_invite_exp_days))
        invites_with_tokens = batch_process_invites(
            db=db,
            survey_id=survey.id,
            emails=body.emails,
            expires_at=invite_expiry,
            batch_size=settings.survey_batch_size
        )
        
        # Prepare data for background task
        invite_ids = [invite.id for _, invite in invites_with_tokens]
        tokens_map = {str(invite.id): token for token, invite in invites_with_tokens}
        
        # Send emails in background
        background_tasks.add_task(
            send_invites_background,
            invite_ids,
            tokens_map,
            survey.name,
            survey.description or ""
        )
    
    # Prepare response
    survey_out = SurveyOut.model_validate(survey)
    survey_out.total_invites = len(invites_with_tokens)
    survey_out.opened_count = 0
    survey_out.submitted_count = 0
    
    # Get schema name if schema_id exists
    if survey.schema_id:
        schema_spec = db.query(SchemaSpecification).filter(
            SchemaSpecification.id == survey.schema_id,
            SchemaSpecification.deleted_at == None
        ).first()
        survey_out.schema_name = schema_spec.schema_name if schema_spec else None
    else:
        survey_out.schema_name = None
    
    return SurveyCreateResponse(
        survey=survey_out,
        invites_sent=len(invites_with_tokens)
    )


# ============ LIST SURVEYS ============

@router.get(
    "",
    response_model=SurveyListResponse,
    summary="List surveys",
    description="""
List all surveys for an account with pagination and filtering.
All account members can view surveys.
"""
)
def list_surveys(
    account_id: UUID,
    status_filter: Optional[SurveyStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    tup=Depends(require_role_for_account({Role.OWNER, Role.ADMIN, Role.MEMBER, Role.VIEWER})),
    db: Session = Depends(get_db),
):
    user, _aid, _role = tup
    
    # Base query
    query = db.query(Survey).filter(
        Survey.account_id == account_id,
        Survey.deleted_at == None
    )
    
    # Apply status filter
    if status_filter:
        query = query.filter(Survey.status == status_filter)
    
    # Get total count
    total = query.count()
    
    # Get paginated results
    surveys = query.order_by(Survey.created_at.desc()).offset(skip).limit(limit).all()
    
    # Add stats to each survey
    survey_outs = []
    for survey in surveys:
        stats = get_survey_stats(db, survey.id)
        survey_out = SurveyOut.model_validate(survey)
        
        # Get schema name if schema_id exists
        if survey.schema_id:
            schema_spec = db.query(SchemaSpecification).filter(
                SchemaSpecification.id == survey.schema_id,
                SchemaSpecification.deleted_at == None
            ).first()
            survey_out.schema_name = schema_spec.schema_name if schema_spec else None
        else:
            survey_out.schema_name = None
        
        survey_out.total_invites = stats["total_invites"]
        survey_out.opened_count = stats["opened_count"]
        survey_out.submitted_count = stats["submitted_count"]
        survey_outs.append(survey_out)
    
    return SurveyListResponse(surveys=survey_outs, total=total)


# ============ GET RECENT SURVEYS ============

@router.get(
    "/recent",
    response_model=SurveyListResponse,
    summary="Get recent surveys",
    description="""
Get the 10 most recent surveys for an account.
All account members can view surveys.
Returns surveys ordered by creation date (newest first).
"""
)
def get_recent_surveys(
    account_id: UUID,
    tup=Depends(require_role_for_account({Role.OWNER, Role.ADMIN, Role.MEMBER, Role.VIEWER})),
    db: Session = Depends(get_db),
):
    user, _aid, _role = tup
    
    # Base query
    query = db.query(Survey).filter(
        Survey.account_id == account_id,
        Survey.deleted_at == None
    )
    
    # Get total count
    total = query.count()
    
    # Get 10 most recent surveys
    surveys = query.order_by(Survey.created_at.desc()).limit(10).all()
    
    # Add stats to each survey
    survey_outs = []
    for survey in surveys:
        stats = get_survey_stats(db, survey.id)
        survey_out = SurveyOut.model_validate(survey)
        
        # Get schema name if schema_id exists
        if survey.schema_id:
            schema_spec = db.query(SchemaSpecification).filter(
                SchemaSpecification.id == survey.schema_id,
                SchemaSpecification.deleted_at == None
            ).first()
            survey_out.schema_name = schema_spec.schema_name if schema_spec else None
        else:
            survey_out.schema_name = None
        
        survey_out.total_invites = stats["total_invites"]
        survey_out.opened_count = stats["opened_count"]
        survey_out.submitted_count = stats["submitted_count"]
        survey_outs.append(survey_out)
    
    return SurveyListResponse(surveys=survey_outs, total=total)


# ============ GET SURVEY OVERVIEW/STATISTICS ============

@router.get(
    "/overview",
    response_model=SurveyOverviewResponse,
    summary="Get survey overview statistics",
    description="""Get survey statistics overview for an account.
    
Returns:
- total_surveys: Total number of surveys (excluding deleted)
- active_surveys: Number of active surveys
- closed_surveys: Number of closed surveys
- total_responses: Total number of survey responses across all surveys

All account members can view overview statistics.
"""
)
def get_survey_overview(
    account_id: UUID,
    tup=Depends(require_role_for_account({Role.OWNER, Role.ADMIN, Role.MEMBER, Role.VIEWER})),
    db: Session = Depends(get_db),
):
    user, _aid, _role = tup
    
    # Count total surveys (excluding deleted)
    total_surveys = db.query(func.count(Survey.id)).filter(
        Survey.account_id == account_id,
        Survey.deleted_at == None
    ).scalar() or 0
    
    # Count active surveys
    active_surveys = db.query(func.count(Survey.id)).filter(
        Survey.account_id == account_id,
        Survey.status == SurveyStatus.ACTIVE,
        Survey.deleted_at == None
    ).scalar() or 0
    
    # Count closed surveys
    closed_surveys = db.query(func.count(Survey.id)).filter(
        Survey.account_id == account_id,
        Survey.status == SurveyStatus.CLOSED,
        Survey.deleted_at == None
    ).scalar() or 0
    
    # Count total responses for all surveys in this account
    # Join with surveys to ensure we only count responses for surveys in this account
    total_responses = db.query(func.count(SurveyResponse.id)).join(
        Survey, SurveyResponse.survey_id == Survey.id
    ).filter(
        Survey.account_id == account_id,
        Survey.deleted_at == None
    ).scalar() or 0
    
    return SurveyOverviewResponse(
        overviews=SurveyOverviewOut(
            total_surveys=total_surveys,
            active_surveys=active_surveys,
            closed_surveys=closed_surveys,
            total_responses=total_responses
        )
    )


# ============ GET SURVEY DETAIL ============

@router.get(
    "/{survey_id}",
    response_model=SurveyDetailOut,
    summary="Get survey details",
    description="""
Get full survey details including all invitations.
All account members can view survey details.
"""
)
def get_survey(
    account_id: UUID,
    survey_id: UUID,
    tup=Depends(require_role_for_account({Role.OWNER, Role.ADMIN, Role.MEMBER, Role.VIEWER})),
    db: Session = Depends(get_db),
):
    user, _aid, _role = tup
    
    survey = db.query(Survey).filter(
        Survey.id == survey_id,
        Survey.account_id == account_id,
        Survey.deleted_at == None
    ).first()
    
    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found"
        )
    
    # Get invites
    invites = db.query(SurveyInvite).filter(
        SurveyInvite.survey_id == survey_id
    ).order_by(SurveyInvite.created_at.desc()).all()
    
    # Build response
    stats = get_survey_stats(db, survey_id)
    survey_out = SurveyDetailOut.model_validate(survey)
    
    # Get schema name if schema_id exists
    if survey.schema_id:
        schema_spec = db.query(SchemaSpecification).filter(
            SchemaSpecification.id == survey.schema_id,
            SchemaSpecification.deleted_at == None
        ).first()
        survey_out.schema_name = schema_spec.schema_name if schema_spec else None
    else:
        survey_out.schema_name = None
    
    survey_out.total_invites = stats["total_invites"]
    survey_out.opened_count = stats["opened_count"]
    survey_out.submitted_count = stats["submitted_count"]
    survey_out.invites = [SurveyInviteOut.model_validate(inv) for inv in invites]
    
    return survey_out


# ============ GET SURVEY STATISTICS ============

@router.get(
    "/{survey_id}/stats",
    response_model=SurveyStatsResponse,
    summary="Get survey statistics",
    description="""Get detailed statistics for a specific survey.
    
Returns:
- survey_id: Survey UUID
- name: Survey name
- status: Survey status (ACTIVE/CLOSED)
- expires_at: Survey expiration date
- stats: Detailed statistics including:
  - total_invites: Total invitations sent
  - opened: Number of invitations opened
  - submitted: Number of responses submitted
  - response_rate: Percentage of responses (submitted/total_invites * 100)
  - expired_invites: Number of expired invitations
  - revoked_invites: Number of revoked invitations

All account members can view survey statistics.
"""
)
def get_survey_stats_endpoint(
    account_id: UUID,
    survey_id: UUID,
    tup=Depends(require_role_for_account({Role.OWNER, Role.ADMIN, Role.MEMBER, Role.VIEWER})),
    db: Session = Depends(get_db),
):
    user, _aid, _role = tup
    
    # Get survey
    survey = db.query(Survey).filter(
        Survey.id == survey_id,
        Survey.account_id == account_id,
        Survey.deleted_at == None
    ).first()
    
    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found"
        )
    
    # Get all invites for this survey
    invites = db.query(SurveyInvite).filter(
        SurveyInvite.survey_id == survey_id
    ).all()
    
    # Calculate statistics
    total_invites = len(invites)
    opened = sum(1 for inv in invites if inv.opened_at is not None)
    submitted = sum(1 for inv in invites if inv.submitted_at is not None)
    
    # Calculate response rate (percentage)
    response_rate = (submitted / total_invites * 100) if total_invites > 0 else 0.0
    response_rate = round(response_rate, 1)  # Round to 1 decimal place
    
    # Count expired invites (expires_at < now and not submitted)
    expired_invites = sum(
        1 for inv in invites 
        if inv.expires_at < now_utc() and inv.submitted_at is None
    )
    
    # Count revoked invites
    revoked_invites = sum(1 for inv in invites if inv.revoked_at is not None)
    
    # Convert status to lowercase string for response
    status_str = survey.status.value.lower() if survey.status else "unknown"
    
    # Convert invites to output format
    invite_outs = [SurveyInviteOut.model_validate(inv) for inv in invites]
    
    return SurveyStatsResponse(
        survey_id=survey.id,
        name=survey.name,
        status=status_str,
        expires_at=survey.expires_at,
        stats=SurveyStatsOut(
            total_invites=total_invites,
            opened=opened,
            submitted=submitted,
            response_rate=response_rate,
            expired_invites=expired_invites,
            revoked_invites=revoked_invites
        ),
        invites=invite_outs
    )


# ============ UPDATE SURVEY ============

@router.put(
    "/{survey_id}",
    response_model=SurveyOut,
    summary="Update survey",
    description="""
Update survey metadata and optionally add new invitations.
Only **OWNER** or **ADMIN** can update surveys.

- If emails are provided, only NEW emails (not already invited) will be sent invitations
- Existing invitations are never resent
"""
)
def update_survey(
    account_id: UUID,
    survey_id: UUID,
    body: SurveyUpdateBody,
    background_tasks: BackgroundTasks,
    tup=Depends(require_role_for_account({Role.OWNER, Role.ADMIN})),
    db: Session = Depends(get_db),
):
    user, _aid, _role = tup
    
    survey = db.query(Survey).filter(
        Survey.id == survey_id,
        Survey.account_id == account_id,
        Survey.deleted_at == None
    ).first()
    
    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found"
        )
    
    # Update fields
    if body.name is not None:
        survey.name = body.name
    if body.description is not None:
        survey.description = body.description
    if body.status is not None:
        survey.status = body.status
    
    survey.updated_at = now_utc()
    
    # Handle new emails
    new_invites_count = 0
    if body.emails:
        new_emails = get_new_emails(db, survey_id, body.emails)
        
        if new_emails:
            invite_expiry = survey.expires_at or (now_utc() + timedelta(days=settings.survey_invite_exp_days))
            invites_with_tokens = batch_process_invites(
                db=db,
                survey_id=survey_id,
                emails=new_emails,
                expires_at=invite_expiry,
                batch_size=settings.survey_batch_size
            )
            
            new_invites_count = len(invites_with_tokens)
            
            # Prepare data for background task
            invite_ids = [invite.id for _, invite in invites_with_tokens]
            tokens_map = {str(invite.id): token for token, invite in invites_with_tokens}
            
            # Send emails in background
            background_tasks.add_task(
                send_invites_background,
                invite_ids,
                tokens_map,
                survey.name,
                survey.description or ""
            )
    
    db.commit()
    db.refresh(survey)
    
    # Build response
    stats = get_survey_stats(db, survey_id)
    survey_out = SurveyOut.model_validate(survey)
    
    # Get schema name if schema_id exists
    if survey.schema_id:
        schema_spec = db.query(SchemaSpecification).filter(
            SchemaSpecification.id == survey.schema_id,
            SchemaSpecification.deleted_at == None
        ).first()
        survey_out.schema_name = schema_spec.schema_name if schema_spec else None
    else:
        survey_out.schema_name = None
    
    survey_out.total_invites = stats["total_invites"]
    survey_out.opened_count = stats["opened_count"]
    survey_out.submitted_count = stats["submitted_count"]
    
    return survey_out


# ============ CLOSE SURVEY ============

@router.post(
    "/{survey_id}/close",
    response_model=SurveyCloseResponse,
    summary="Close survey",
    description="""
Close a survey to prevent further submissions.
Only **OWNER** or **ADMIN** can close surveys.
"""
)
def close_survey(
    account_id: UUID,
    survey_id: UUID,
    tup=Depends(require_role_for_account({Role.OWNER, Role.ADMIN})),
    db: Session = Depends(get_db),
):
    user, _aid, _role = tup
    
    survey = db.query(Survey).filter(
        Survey.id == survey_id,
        Survey.account_id == account_id,
        Survey.deleted_at == None
    ).first()
    
    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found"
        )
    
    survey.status = SurveyStatus.CLOSED
    survey.updated_at = now_utc()
    
    db.commit()
    
    return SurveyCloseResponse()


# ============ DELETE SURVEY (SOFT DELETE) ============

@router.delete(
    "/{survey_id}",
    response_model=MessageResponse,
    summary="Delete survey",
    description="""
Soft delete a survey (sets deleted_at timestamp).
Only **OWNER** can delete surveys.
"""
)
def delete_survey(
    account_id: UUID,
    survey_id: UUID,
    tup=Depends(require_role_for_account({Role.OWNER})),
    db: Session = Depends(get_db),
):
    user, _aid, _role = tup
    
    survey = db.query(Survey).filter(
        Survey.id == survey_id,
        Survey.account_id == account_id,
        Survey.deleted_at == None
    ).first()
    
    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found"
        )
    
    survey.deleted_at = now_utc()
    db.commit()
    
    return MessageResponse(message="Survey deleted successfully")


# ============ REVOKE SURVEY INVITE ============

@router.post(
    "/{survey_id}/invites/{invite_id}/revoke",
    response_model=MessageResponse,
    summary="Revoke survey invitation",
    description="""
Revoke a survey invitation to prevent the recipient from submitting.
Only **OWNER** or **ADMIN** can revoke invitations.

- Sets revoked_at timestamp on the invite
- Prevents the invite from being used to submit a survey
- Cannot revoke if already submitted
"""
)
def revoke_survey_invite(
    account_id: UUID,
    survey_id: UUID,
    invite_id: UUID,
    tup=Depends(require_role_for_account({Role.OWNER, Role.ADMIN})),
    db: Session = Depends(get_db),
):
    user, _aid, _role = tup
    
    # Verify survey belongs to account
    survey = db.query(Survey).filter(
        Survey.id == survey_id,
        Survey.account_id == account_id,
        Survey.deleted_at == None
    ).first()
    
    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found"
        )
    
    # Get the invite
    invite = db.query(SurveyInvite).filter(
        SurveyInvite.id == invite_id,
        SurveyInvite.survey_id == survey_id
    ).first()
    
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey invite not found"
        )
    
    # Check if already submitted
    if invite.submitted_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot revoke invite - survey already submitted"
        )
    
    # Check if already revoked
    if invite.revoked_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invite already revoked"
        )
    
    # Revoke the invite
    invite.revoked_at = now_utc()
    db.commit()
    
    return MessageResponse(message=f"Invitation to {invite.email} has been revoked successfully")


# ============ GET SURVEY RESPONSES ============

@router.get(
    "/{survey_id}/responses",
    response_model=SurveyResponseListResponse,
    summary="Get all survey responses",
    description="""
Get all responses for a survey with pagination.
Only **OWNER** or **ADMIN** can view responses.
"""
)
def get_survey_responses(
    account_id: UUID,
    survey_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    tup=Depends(require_role_for_account({Role.OWNER, Role.ADMIN})),
    db: Session = Depends(get_db),
):
    user, _aid, _role = tup
    
    # Verify survey belongs to account
    survey = db.query(Survey).filter(
        Survey.id == survey_id,
        Survey.account_id == account_id,
        Survey.deleted_at == None
    ).first()
    
    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found"
        )
    
    # Get responses with pagination, join with invite to get email and sent_at
    responses = db.query(SurveyResponse).filter(
        SurveyResponse.survey_id == survey_id
    ).order_by(SurveyResponse.submitted_at.desc()).offset(skip).limit(limit).all()
    
    total = db.query(func.count(SurveyResponse.id)).filter(
        SurveyResponse.survey_id == survey_id
    ).scalar()
    
    # Transform response data to row format and add invite details
    response_outs = []
    for r in responses:
        response_out = SurveyResponseOut.model_validate(r)
        
        # Get invite details
        invite = db.query(SurveyInvite).filter(
            SurveyInvite.id == r.invite_id
        ).first()
        
        if invite:
            response_out.email = invite.email
            response_out.sent_at = invite.sent_at
        
        # Get schema name if schema_id exists
        if r.schema_id:
            schema_spec = db.query(SchemaSpecification).filter(
                SchemaSpecification.id == r.schema_id,
                SchemaSpecification.deleted_at == None
            ).first()
            response_out.schema_name = schema_spec.schema_name if schema_spec else None
        
        # Transform response_data from columnar to row format
        response_out.response_data = transform_response_data_to_rows(response_out.response_data)
        response_outs.append(response_out)
    
    return SurveyResponseListResponse(
        responses=response_outs,
        total=total
    )


@router.get(
    "/{survey_id}/responses/invite/{invite_id}",
    response_model=SurveyResponseDetailResponse,
    summary="Get a specific survey response by invite ID",
    description="""
Get a specific survey response by the survey invite ID.
Only **OWNER** or **ADMIN** can view responses.
"""
)
def get_survey_response(
    account_id: UUID,
    survey_id: UUID,
    invite_id: UUID,
    tup=Depends(require_role_for_account({Role.OWNER, Role.ADMIN})),
    db: Session = Depends(get_db),
):
    user, _aid, _role = tup
    
    # Verify survey belongs to account
    survey = db.query(Survey).filter(
        Survey.id == survey_id,
        Survey.account_id == account_id,
        Survey.deleted_at == None
    ).first()
    
    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found"
        )
    
    # Verify invite belongs to survey
    invite = db.query(SurveyInvite).filter(
        SurveyInvite.id == invite_id,
        SurveyInvite.survey_id == survey_id
    ).first()
    
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey invite not found"
        )
    
    # Get the specific response by invite_id
    response = db.query(SurveyResponse).filter(
        SurveyResponse.invite_id == invite_id,
        SurveyResponse.survey_id == survey_id
    ).first()
    
    if not response:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey response not found for this invite"
        )
    
    response_out = SurveyResponseOut.model_validate(response)
    
    # Add invite details
    response_out.email = invite.email
    response_out.sent_at = invite.sent_at
    
    # Get schema name if schema_id exists
    if response.schema_id:
        schema_spec = db.query(SchemaSpecification).filter(
            SchemaSpecification.id == response.schema_id,
            SchemaSpecification.deleted_at == None
        ).first()
        response_out.schema_name = schema_spec.schema_name if schema_spec else None
    
    # Transform response_data from columnar to row format
    response_out.response_data = transform_response_data_to_rows(response_out.response_data)
    
    return SurveyResponseDetailResponse(response=response_out)
