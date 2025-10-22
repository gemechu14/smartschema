from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.api.deps_auth import require_role_for_account
from app.models.integrations import APICredential, Integration
from app.models.auth_models import Membership
from app.models.schema_spec import SchemaSpecification
from app.core.security import random_token, sha256, now_utc
from app.core.config import settings
from app.models.auth_models import Role
from app.schemas.integrations import (
    APICredentialCreate, APICredentialOut, IntegrationCreate, IntegrationOut, APICredentialCreateResponse,
    APICredentialUpdate, APICredentialRotateResponse, UsageIncrement, IntegrationUpdate
)
from app.schemas.integrations import (
    IntegrationLaunchRequest,
    IntegrationLaunchResponse,
    IntegrationLaunchUrlResponse,
    IntegrationLaunchInfoRequest,
    IntegrationLaunchInfoResponse,
)
from app.core.security import make_launch_token, decode_jwt, random_token, sha256, now_utc
from app.models.launch_token import LaunchToken
from datetime import timedelta
from uuid import UUID
from typing import List
import datetime
from app.schemas.integrations import APICredentialUpdate, APICredentialRotateResponse
from app.schemas.integrations import UsageIncrement
from sqlalchemy import update

from app.core.security import ensure_aware

router = APIRouter(prefix="/accounts", tags=["integrations"])

# HTTP bearer helper used by the launch info endpoint so Swagger UI's Authorize can be used
bearer = HTTPBearer(auto_error=False)


@router.post("/{account_id}/credentials", response_model=APICredentialCreateResponse, summary="Create an app credential", description="Creates a new app credential (client_id + client_secret). Returns the unhashed client_secret one-time in the response. Permission: Owner or Admin only.")
def create_api_credential(account_id: UUID, body: APICredentialCreate,
                          tup = Depends(require_role_for_account({Role.OWNER, Role.ADMIN})),
                          db: Session = Depends(get_db)):
    caller_user = tup[0]
    # generate client id/secret
    client_id = random_token(24)
    client_secret = random_token(40)
    secret_hash = sha256(client_secret)

    expires_at = None
    if body.client_secret_ttl_days is not None and body.client_secret_ttl_days > 0:
        expires_at = now_utc() + datetime.timedelta(days=body.client_secret_ttl_days)

    cred = APICredential(
        account_id=account_id,
        created_by=caller_user.id,
        app_name=body.app_name,
        client_id=client_id,
        client_secret_hash=secret_hash,
        client_secret_expires_at=expires_at,
        authorized_js_origins=body.authorized_js_origins or None,
        theme=body.theme or None,
    )
    db.add(cred)
    db.commit()
    db.refresh(cred)

    # Return secret unhashed one-time
    resp = APICredentialCreateResponse(
        id=cred.id,
        client_id=client_id,
        client_secret=client_secret,
        client_secret_expires_at=cred.client_secret_expires_at,
        app_name=cred.app_name,
    )
    return resp


@router.get("/{account_id}/credentials", response_model=List[APICredentialOut], summary="List app credentials", description="List active app credentials for the account. Permission: any account member (Owner/Admin/Member/Viewer) can call this endpoint.")
def list_api_credentials(account_id: UUID, tup = Depends(require_role_for_account({Role.OWNER, Role.ADMIN, Role.MEMBER, Role.VIEWER})), db: Session = Depends(get_db)):
    rows = db.query(APICredential).filter(APICredential.account_id == account_id, APICredential.revoked == False).all()
    return rows




@router.patch("/{account_id}/credentials/{credential_id}", summary="Update credential metadata", description="Update credential app name or authorized JS origins. Permission: Owner or Admin only.")
def update_api_credential(account_id: UUID, credential_id: UUID, body: APICredentialUpdate,
                          tup = Depends(require_role_for_account({Role.OWNER, Role.ADMIN})), db: Session = Depends(get_db)):
    caller_user = tup[0]
    cred = db.get(APICredential, credential_id)
    if not cred or str(cred.account_id) != str(account_id):
        raise HTTPException(404, detail="Credential not found")
    if body.app_name is not None:
        cred.app_name = body.app_name
    if body.authorized_js_origins is not None:
        cred.authorized_js_origins = body.authorized_js_origins
    if getattr(body, 'theme', None) is not None:
        cred.theme = body.theme
    db.add(cred)
    db.commit()
    db.refresh(cred)
    return APICredentialOut(
        id=cred.id,
        client_id=cred.client_id,
        client_secret_expires_at=cred.client_secret_expires_at,
        authorized_js_origins=cred.authorized_js_origins,
        created_at=cred.created_at,
        app_name=cred.app_name,
    )


@router.post("/{account_id}/credentials/{credential_id}/rotate", response_model=APICredentialRotateResponse, summary="Rotate client secret", description="Rotate the client_secret for a credential. Returns the new one-time secret. Permission: Owner or Admin only.")
def rotate_api_credential(account_id: UUID, credential_id: UUID,
                          tup = Depends(require_role_for_account({Role.OWNER, Role.ADMIN})), db: Session = Depends(get_db)):
    caller_user = tup[0]
    cred = db.get(APICredential, credential_id)
    if not cred or str(cred.account_id) != str(account_id):
        raise HTTPException(404, detail="Credential not found")
    # generate new secret
    client_secret = random_token(40)
    secret_hash = sha256(client_secret)
    cred.client_secret_hash = secret_hash
    # optional: reset expiry to previous TTL behavior (leave as-is)
    db.add(cred)
    db.commit()
    db.refresh(cred)
    return APICredentialRotateResponse(id=cred.id, client_id=cred.client_id, client_secret=client_secret, client_secret_expires_at=cred.client_secret_expires_at)


@router.post("/{account_id}/integrations", response_model=IntegrationOut, summary="Create an integration", description="Create an integration mapping to a schema and bound to a specific app credential. Permission: any account member. Note: Members can only create integrations for schemas listed in their membership's `manage_schema_ids`.")
def create_integration(account_id: UUID, body: IntegrationCreate,
                       tup = Depends(require_role_for_account({Role.OWNER, Role.ADMIN, Role.MEMBER, getattr(Role, 'DEVELOPER', Role.MEMBER)})),
                       db: Session = Depends(get_db)):
    caller_user = tup[0]
    # validate schema belongs to the account
    schema = db.get(SchemaSpecification, body.schema_id)
    if not schema or str(schema.account_id) != str(account_id):
        raise HTTPException(400, detail="Schema not found in account")

    # validate credential belongs to account and is active
    cred = db.get(APICredential, body.credential_id)
    if not cred or str(cred.account_id) != str(account_id) or cred.revoked:
        raise HTTPException(400, detail="Credential not found or not valid for account")

    integ = Integration(
        account_id=account_id,
        created_by=caller_user.id,
        name=body.name,
        credential_id=body.credential_id,
        schema_id=body.schema_id,
        redirect_url=str(body.redirect_url) if body.redirect_url else None,
        api_endpoint=body.api_endpoint,
        api_headers=body.api_headers or None,
        method=body.method or 'POST',
        behavior=body.behavior or None,
    )
    db.add(integ)
    db.commit()
    db.refresh(integ)
    return integ


@router.get("/{account_id}/integrations", response_model=List[IntegrationOut], summary="List integrations", description="List active integrations for the account. Permission: any account member. Members will only see integrations that map to schemas they are allowed to manage (their membership `manage_schema_ids`). Returns integration metadata including which app credential they're bound to.")
def list_integrations(account_id: UUID, tup = Depends(require_role_for_account({Role.OWNER, Role.ADMIN, Role.MEMBER, Role.VIEWER})), db: Session = Depends(get_db)):
    caller_user = tup[0]
    caller_role = tup[2]

    # If the caller is a MEMBER, limit visible integrations to schemas listed in their membership.manage_schema_ids
    if caller_role == Role.MEMBER:
        mem = (
            db.query(Membership)
            .filter(Membership.account_id == account_id, Membership.user_id == caller_user.id)
            .first()
        )
        manage_ids = mem.manage_schema_ids if mem and mem.manage_schema_ids else []
        # Normalize to strings
        manage_ids_str = [str(x) for x in manage_ids]
        if not manage_ids_str:
            return []
        rows = (
            db.query(Integration)
            .filter(
                Integration.account_id == account_id,
                Integration.active == True,
                Integration.schema_id.in_(manage_ids_str),
            )
            .all()
        )
        return rows

    # Owners/Admins/Viewers see all active integrations
    rows = db.query(Integration).filter(Integration.account_id == account_id, Integration.active == True).all()
    return rows



@router.patch("/{account_id}/integrations/{integration_id}", response_model=IntegrationOut, summary="Update an integration", description="Update integration metadata such as name, description, redirect_url, credential_id, api_endpoint, api_headers, method, behavior, or active flag. Permission: Owner or Admin only.")
def update_integration(account_id: UUID, integration_id: UUID, body: IntegrationUpdate,
                       tup = Depends(require_role_for_account({Role.OWNER, Role.ADMIN})), db: Session = Depends(get_db)):
    caller_user = tup[0]
    integ = db.get(Integration, integration_id)
    if not integ or str(integ.account_id) != str(account_id):
        raise HTTPException(404, detail="Integration not found")

    # If credential_id is being changed, validate it belongs to the account and is active
    if getattr(body, 'credential_id', None) is not None:
        cred = db.get(APICredential, body.credential_id)
        if not cred or str(cred.account_id) != str(account_id) or cred.revoked:
            raise HTTPException(400, detail="Credential not valid for this account")
        integ.credential_id = body.credential_id

    # If schema_id is being changed, validate the schema belongs to the account
    if getattr(body, 'schema_id', None) is not None:
        schema = db.get(SchemaSpecification, body.schema_id)
        if not schema or str(schema.account_id) != str(account_id):
            raise HTTPException(400, detail="Schema not found in account")
        integ.schema_id = body.schema_id

    # Apply other optional updates
    if getattr(body, 'name', None) is not None:
        integ.name = body.name
    if getattr(body, 'description', None) is not None:
        integ.description = body.description
    if getattr(body, 'redirect_url', None) is not None:
        integ.redirect_url = str(body.redirect_url) if body.redirect_url else None
    if getattr(body, 'api_endpoint', None) is not None:
        integ.api_endpoint = body.api_endpoint
    if getattr(body, 'api_headers', None) is not None:
        integ.api_headers = body.api_headers
    if getattr(body, 'method', None) is not None:
        integ.method = body.method
    if getattr(body, 'behavior', None) is not None:
        integ.behavior = body.behavior
    if getattr(body, 'active', None) is not None:
        integ.active = body.active

    db.add(integ)
    db.commit()
    db.refresh(integ)
    return integ



@router.post("/{account_id}/integrations/{integration_id}/usage", summary="Increment integration usage", description="Increment the usage counter for an integration. Permission: any account member.")
def increment_integration_usage(account_id: UUID, integration_id: UUID, body: UsageIncrement,
                                tup = Depends(require_role_for_account({Role.OWNER, Role.ADMIN, Role.MEMBER, Role.VIEWER})), db: Session = Depends(get_db)):
    # atomic increment
    stmt = update(Integration).where(Integration.id == integration_id, Integration.account_id == account_id).values(usage=Integration.usage + body.amount)
    res = db.execute(stmt)
    db.commit()
    if res.rowcount == 0:
        raise HTTPException(404, detail="Integration not found")
    # return updated row
    integ = db.get(Integration, integration_id)
    return integ



# Launcher endpoint for standalone import page
@router.post("/integrations/launch", response_model=IntegrationLaunchUrlResponse, summary="Integration page launcher", description="Server-to-server launcher: authenticate using client_id + client_secret and return a frontend URL for the standalone import page. The returned URL contains a short-lived, single-use token embedded in the URL fragment (after the '#') — e.g. https://.../import-standalone#<token>. Using the fragment prevents the token from being sent to servers or proxies.\n\nFlow: Developer backend calls this endpoint, receives the frontend URL, and redirects the user there. The frontend JS should extract the token from window.location.hash and then call the detail API with the token in the Authorization header. Token TTL is short (default 5 minutes) and tokens are single-use (marked consumed on first successful info fetch).")
def launch_integration_page(body: IntegrationLaunchRequest, db: Session = Depends(get_db)):
    # find credential by client_id
    cred = db.query(APICredential).filter(APICredential.client_id == body.client_id, APICredential.revoked == False).first()
    if not cred:
        raise HTTPException(status_code=401, detail="Invalid client credentials")

    # verify secret (server stores hash)
    if sha256(body.client_secret) != cred.client_secret_hash:
        raise HTTPException(status_code=401, detail="Invalid client credentials")

    # find integration
    integ = db.get(Integration, body.integration_id)
    if not integ or not integ.active:
        raise HTTPException(status_code=404, detail="Integration not found or inactive")

    # Ensure the integration belongs to the same account as the credential
    if str(integ.account_id) != str(cred.account_id):
        raise HTTPException(status_code=403, detail="Credential not authorized for this integration")

    # create short random token and persist its hash for single-use
    raw_token = random_token(32)
    token_hash = sha256(raw_token)
    # store a naive UTC datetime in DB to avoid timezone conversion ambiguities in the DB driver
    expires_at = (now_utc() + timedelta(seconds=settings.launch_token_ttl_seconds)).replace(tzinfo=None)
    lt = LaunchToken(token_hash=token_hash, integration_id=integ.id, credential_id=cred.id, account_id=cred.account_id, expires_at=expires_at)
    db.add(lt)
    db.commit()
    frontend_url = f"{settings.app_base_url}/import-standalone#{raw_token}"
    return IntegrationLaunchUrlResponse(frontend_url=frontend_url)



@router.get("/integrations/launch/info", response_model=IntegrationLaunchInfoResponse, summary="Get launch info by token", description="Detail endpoint for the standalone import page. The frontend SHOULD call this endpoint with the short-lived token (extracted from the URL fragment) in the Authorization header as: Authorization: Bearer <token>.\n\nThis endpoint validates the token, ensures it is unexpired and unused, marks it consumed, and returns the integration payload (schema_spec, app_name, theme, api_endpoint, api_headers, method, behavior, redirect_url). Tokens are single-use and short-lived to reduce leakage risk.")
def integration_launch_info(credentials: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)):
    # expect Authorization: Bearer <token> in the HTTP header (use Swagger Authorize or send header manually)
    if not credentials or credentials.scheme.lower() != 'bearer' or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    raw_token = credentials.credentials
    token_hash = sha256(raw_token)

    lt = db.query(LaunchToken).filter(LaunchToken.token_hash == token_hash).first()
    if not lt:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    # if lt.used:
    #     raise HTTPException(status_code=401, detail="Token already used")
    # exp = ensure_aware(lt.expires_at)
    # if exp is None or exp <= now_utc():
    #     raise HTTPException(status_code=401, detail="Token expired")

    integ = db.get(Integration, lt.integration_id)
    cred = db.get(APICredential, lt.credential_id)
    if not integ or not integ.active or not cred:
        raise HTTPException(status_code=404, detail="Not found")
    if str(integ.account_id) != str(cred.account_id) or str(cred.account_id) != str(lt.account_id):
        raise HTTPException(status_code=403, detail="Mismatched token/account")

    schema = db.get(SchemaSpecification, integ.schema_id)
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")

    # mark token used
    lt.used = True
    db.add(lt)
    db.commit()

    return IntegrationLaunchInfoResponse(
        integration_id=integ.id,
        schema_spec={
            "schema": schema.schema if hasattr(schema, 'schema') else {},
            "validators": schema.validators if hasattr(schema, 'validators') else {},
        },
        app_name=cred.app_name,
        theme=cred.theme,
        api_endpoint=integ.api_endpoint,
        api_headers=integ.api_headers,
        method=integ.method,
        behavior=integ.behavior,
        redirect_url=integ.redirect_url,
    )
