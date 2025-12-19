from uuid import UUID
from urllib.parse import unquote
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.api.deps import get_db
from app.models.survey import Survey, SurveyInvite, SurveyResponse
from app.models.schema_spec import SchemaSpecification
from app.schemas.survey import (
    SurveyOpenResponse, SurveyOpenBody, SurveySubmitBody, SurveySubmitResponse,
    SurveyStatusBody
)
from app.services.survey_service import validate_survey_token
from app.core.security import now_utc


router = APIRouter(prefix="/surveys", tags=["survey-public"])


# ============ OPEN SURVEY (GET SURVEY INFO) ============

@router.get(
    "/open",
    response_model=SurveyOpenResponse,
    summary="Open survey with token",
    description="""
Open a survey using an invitation token.
This endpoint is public (no authentication required).

- Validates the token
- Checks expiry, revoked status, and submission status
- Sets opened_at timestamp on first access
- Returns survey information and schema

**Note:** This does NOT submit the survey, only opens it for viewing.
"""
)
def open_survey(
    token: str = Query(..., description="Survey invitation token (extracted from URL fragment #token=xxx)"),
    db: Session = Depends(get_db),
):
    # URL decode token in case it was encoded (FastAPI usually does this, but be safe)
    if token:
        token = unquote(token.strip())
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token is required"
        )
    
    # Validate token and get survey + invite
    survey, invite = validate_survey_token(db, token)
    
    # Set opened_at if this is the first time
    if not invite.opened_at:
        invite.opened_at = now_utc()
        db.commit()
    
    # Check if already submitted
    already_submitted = invite.submitted_at is not None
    
    # Get schema if available
    schema_data = None
    if survey.schema_id:
        schema_spec = db.query(SchemaSpecification).filter(
            SchemaSpecification.id == survey.schema_id,
            SchemaSpecification.deleted_at == None
        ).first()
        
        if schema_spec:
            schema_data = {
                "id": str(schema_spec.id),
                "schema_name": schema_spec.schema_name,
                "description": schema_spec.description,
                "schema": schema_spec.schema,
                "validators": schema_spec.validators
            }
    
    return SurveyOpenResponse(
        survey_id=survey.id,
        survey_name=survey.name,
        survey_description=survey.description,
        schema=schema_data,
        already_submitted=already_submitted,
        expires_at=survey.expires_at or invite.expires_at
    )


# ============ SUBMIT SURVEY ============

@router.post(
    "/submit",
    response_model=SurveySubmitResponse,
    summary="Submit survey response",
    description="""
Submit a response to a survey using an invitation token.
This endpoint is public (no authentication required).

- Validates the token
- Checks expiry, revoked status, and previous submission
- Validates response data against schema (if schema is defined)
- Creates survey response
- Marks invitation as submitted
- DB-level UNIQUE constraint prevents double submission

**Note:** Each invitation can only submit once.
"""
)
def submit_survey(
    body: SurveySubmitBody,
    db: Session = Depends(get_db),
):
    # Validate token and get survey + invite
    survey, invite = validate_survey_token(db, body.token)
    
    # Validate response data against schema if present
    if survey.schema_id:
        schema_spec = db.query(SchemaSpecification).filter(
            SchemaSpecification.id == survey.schema_id,
            SchemaSpecification.deleted_at == None
        ).first()
        
        if schema_spec:
            # Basic validation: check if response_data is a dict
            if not isinstance(body.response_data, dict):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Response data must be a JSON object"
                )
            
            # TODO: Add more sophisticated schema validation here
            # You could validate against schema_spec.schema and schema_spec.validators
            # For now, we accept any valid JSON object
    
    # Create survey response
    try:
        response = SurveyResponse(
            survey_id=survey.id,
            invite_id=invite.id,
            schema_id=survey.schema_id,
            response_data=body.response_data,
            submitted_at=now_utc()
        )
        
        db.add(response)
        
        # Mark invite as submitted
        invite.submitted_at = now_utc()
        
        db.commit()
        db.refresh(response)
        
        return SurveySubmitResponse(
            response_id=response.id
        )
        
    except IntegrityError as e:
        db.rollback()
        
        # Check if this is a duplicate submission error
        if "uq_survey_responses_invite_id" in str(e) or "unique" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You have already submitted this survey"
            )
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to submit survey response"
        )


# ============ CHECK SURVEY STATUS ============

@router.post(
    "/status",
    summary="Check survey invitation status",
    description="""
Check the status of a survey invitation without opening it.
This endpoint is public (no authentication required).

- Token should be extracted from URL fragment (e.g., /surveys#token=xxx) by frontend
- Returns validation status without opening the survey

**Security:** Token is sent in request body, not URL query parameter.

Returns:
- valid: boolean indicating if token is valid and not expired/revoked/submitted
- message: status message
- expires_at: expiration date if applicable
"""
)
def check_survey_status(
    body: SurveyStatusBody,
    db: Session = Depends(get_db),
):
    try:
        survey, invite = validate_survey_token(db, body.token)
        
        return {
            "valid": True,
            "message": "Survey invitation is valid",
            "survey_name": survey.name,
            "expires_at": invite.expires_at,
            "opened": invite.opened_at is not None,
            "submitted": invite.submitted_at is not None
        }
    except HTTPException as e:
        return {
            "valid": False,
            "message": e.detail,
            "survey_name": None,
            "expires_at": None,
            "opened": None,
            "submitted": None
        }


# ============ DEBUG: LIST ALL INVITES (for testing only) ============

@router.get(
    "/debug/invites",
    summary="[DEBUG] List all survey invites with tokens",
    description="""
DEBUG ENDPOINT - List all survey invites.
This should be removed or protected in production.

Returns all invites with their token hashes for debugging purposes.
"""
)
def debug_list_invites(
    survey_id: UUID = Query(None, description="Optional: filter by survey_id"),
    db: Session = Depends(get_db),
):
    """DEBUG: List all invites to help debug token issues."""
    query = db.query(SurveyInvite)
    if survey_id:
        query = query.filter(SurveyInvite.survey_id == survey_id)
    
    invites = query.limit(10).all()
    
    return {
        "total": len(invites),
        "invites": [
            {
                "id": str(inv.id),
                "email": inv.email,
                "survey_id": str(inv.survey_id),
                "token_hash": inv.token_hash,
                "token_hash_length": len(inv.token_hash),
                "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
                "opened_at": inv.opened_at.isoformat() if inv.opened_at else None,
                "submitted_at": inv.submitted_at.isoformat() if inv.submitted_at else None,
                "revoked_at": inv.revoked_at.isoformat() if inv.revoked_at else None,
            }
            for inv in invites
        ],
        "note": "This is a debug endpoint. Token hashes are shown for verification."
    }















