from datetime import timedelta
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.deps_auth import require_role_for_account  # <-- new dep (path-only)
from app.core.config import settings
from app.core.security import random_token, sha256, now_utc
from app.models.auth_models import Account, Membership, Role, User, Invitation
from app.models.schema_spec import SchemaSpecification
from app.schemas.auth import InviteMemberBody, MemberOut, AccountRename, MemberUpdatePermissions
from app.services.mailer import send_email

router = APIRouter(prefix="/accounts", tags=["accounts"])


# ---------- GET ACCOUNT (Owner only; replaces 'current') ----------
@router.get(
    "/{account_id}",
    summary="Get account (Owner only)",
    description="Returns the account identified by the path parameter. Owner only."
)
def get_account(
    account_id: UUID,
    tup = Depends(require_role_for_account({Role.OWNER})),
    db: Session = Depends(get_db),
):
    # require_role_for_account has already verified membership+role against path account_id
    acc = db.get(Account, account_id)
    if not acc:
        raise HTTPException(404, "Account not found")
    return {"id": str(acc.id), "name": acc.name}


# ---------- LIST MEMBERS ----------
@router.get(
    "/{account_id}/members",
    response_model=list[MemberOut],
    summary="List members (Owner only)",
    description="Lists all members in the account. Requires Owner role."
)
def list_members(
    account_id: UUID,
    tup = Depends(require_role_for_account({Role.OWNER})),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Membership, User)
        .join(User, User.id == Membership.user_id)
        .filter(Membership.account_id == account_id)
        .all()
    )
    return [
        MemberOut(
            user_id=u.id,
            email=u.email,
            role=m.role,
            first_name=u.first_name,
            last_name=u.last_name
        )
        for (m, u) in rows
    ]


# ---------- CHANGE ROLE ----------
@router.patch(
    "/{account_id}/members/{user_id}",
    summary="Change a member's role (Owner only)",
    description="Owner can change a member's role. Cannot demote the last remaining Owner."
)
def change_role(
    account_id: UUID,
    user_id: UUID,
    role: Role,
    tup = Depends(require_role_for_account({Role.OWNER})),
    db: Session = Depends(get_db),
):
    user, _aid, _role = tup

    # prevent removing last OWNER (including self-demote)
    if role != Role.OWNER:
        owners = (
            db.query(Membership)
            .filter(Membership.account_id == account_id, Membership.role == Role.OWNER)
            .count()
        )
        if owners <= 1 and user_id == user.id:
            raise HTTPException(400, "Cannot demote the last OWNER")

    m = (
        db.query(Membership)
        .filter(Membership.account_id == account_id, Membership.user_id == user_id)
        .first()
    )
    if not m:
        raise HTTPException(404, "Membership not found")

    m.role = role
    db.commit()
    return {"ok": True}


# ---------- REMOVE MEMBER ----------
@router.delete(
    "/{account_id}/members/{user_id}",
    summary="Remove a member (Owner only)",
    description="Owner can remove a member. Cannot remove the last remaining Owner."
)
def remove_member(
    account_id: UUID,
    user_id: UUID,
    tup = Depends(require_role_for_account({Role.OWNER})),
    db: Session = Depends(get_db),
):
    victim = (
        db.query(Membership)
        .filter(Membership.account_id == account_id, Membership.user_id == user_id)
        .first()
    )
    if not victim:
        raise HTTPException(404, "Membership not found")

    if victim.role == Role.OWNER:
        owners = (
            db.query(Membership)
            .filter(Membership.account_id == account_id, Membership.role == Role.OWNER)
            .count()
        )
        if owners <= 1:
            raise HTTPException(400, "Cannot remove the last OWNER")

    db.delete(victim)
    db.commit()
    return {"ok": True}


# ---------- INVITE ----------
@router.post(
    "/{account_id}/invite",
    summary="Invite a member (Owner only)",
    description="""
Sends an invitation email to join this account as the specified role.  
If `manage_schema_ids` is provided, those schema permissions are pre-applied on acceptance.  
Admins/Owners ignore per-schema restrictions.
""",
)
def invite_member(
    account_id: UUID,
    body: InviteMemberBody,
    tup = Depends(require_role_for_account({Role.OWNER})),
    db: Session = Depends(get_db),
):
    # --- normalize and validate manage_schema_ids (List[UUID] -> List[str]) ---
    raw_ids = body.manage_schema_ids or []
    normalized: list[str] = []
    for x in raw_ids:
        try:
            normalized.append(str(UUID(str(x))))
        except Exception:
            raise HTTPException(400, detail=f"Invalid schema id: {x}")

    # ensure schemas belong to this account (prevents cross-tenant leakage)
    if normalized:
        existing = {
            str(r[0])
            for r in db.query(SchemaSpecification.id)
                       .filter(SchemaSpecification.account_id == account_id,
                               SchemaSpecification.id.in_(normalized))
                       .all()
        }
        missing = [sid for sid in normalized if sid not in existing]
        if missing:
            raise HTTPException(400, detail=f"Schema ids not in this account: {missing}")

    # dedupe while preserving order
    seen = set()
    normalized_unique = [sid for sid in normalized if not (sid in seen or seen.add(sid))]

    # --- create invite ---
    raw = random_token(32)
    inv = Invitation(
        account_id=account_id,
        email=str(body.email).lower().strip(),
        role=Role(body.role),
        token_hash=sha256(raw),
        expires_at=now_utc() + timedelta(days=settings.invite_exp_days),
        manage_schema_ids=normalized_unique or None,  # <- JSON-serializable
    )
    db.add(inv)
    db.commit()

    # email
    link = f"{settings.app_base_url}/auth/signup?invite={raw}&email={inv.email}"
    html = f"""
      <p>You’ve been invited to join an account on {settings.app_name} as <b>{inv.role}</b>.</p>
      <p><a href="{link}">Accept invitation</a></p>
      <p>If the button doesn't work, paste this URL:<br>{link}</p>
    """
    send_email(to_email=inv.email, subject=f"You're invited to {settings.app_name}", html=html)
    return {"ok": True, "message": "Invitation sent."}


# ---------- PREVIEW INVITE (public) ----------
@router.get(
    "/invites/{token}",
    summary="Preview invite (public)",
    description="Returns invite info if valid and unexpired. Useful for signup screens."
)
def preview_invite(token: str, db: Session = Depends(get_db)):
    inv = db.query(Invitation).filter(Invitation.token_hash == sha256(token)).first()
    if not inv or inv.expires_at < now_utc():
        raise HTTPException(404, "Invite not found or expired")
    return {"email": inv.email, "role": inv.role, "account_id": str(inv.account_id)}


# ---------- RENAME ACCOUNT ----------
@router.patch(
    "/{account_id}",
    summary="Rename account (Owner only)",
    description="Owner can rename the account."
)
def rename_account(
    account_id: UUID,
    body: AccountRename,
    tup = Depends(require_role_for_account({Role.OWNER})),
    db: Session = Depends(get_db),
):
    acc = db.get(Account, account_id)
    if not acc:
        raise HTTPException(404, "Account not found")

    acc.name = body.name.strip()
    db.commit()
    return {"ok": True, "id": str(acc.id), "name": acc.name}


@router.put(
    "/{account_id}/members/{member_user_id}/permissions",
    summary="Update a member's allowed schemas (Owner only)",
    description="""
Replace the per-schema management list for a MEMBER/VIEWER.  
Owners/Admins always manage all schemas and ignore this list.
""",
)
def update_member_permissions(
    account_id: UUID,
    member_user_id: UUID,
    body: MemberUpdatePermissions,
    tup = Depends(require_role_for_account({Role.OWNER})),
    db: Session = Depends(get_db),
):
    mem = (
        db.query(Membership)
        .filter(Membership.account_id == account_id, Membership.user_id == member_user_id)
        .first()
    )
    if not mem:
        raise HTTPException(404, "Membership not found")

    # Normalize to strings (JSON-serializable), drop invalids, dedupe
    raw_ids = body.manage_schema_ids or []
    normalized: list[str] = []
    for x in raw_ids:
        try:
            # accept either UUID or string-like and store as canonical string
            normalized.append(str(UUID(str(x))))
        except Exception:
            raise HTTPException(400, detail=f"Invalid schema id: {x}")

    # (Optional but recommended) ensure each schema actually belongs to this account
    if normalized:
        existing = {
            str(r[0])
            for r in db.query(SchemaSpecification.id)
                      .filter(SchemaSpecification.account_id == account_id,
                              SchemaSpecification.id.in_(normalized))
                      .all()
        }
        missing = [sid for sid in normalized if sid not in existing]
        if missing:
            raise HTTPException(400, detail=f"Schema ids not in this account: {missing}")

    # Deduplicate while preserving order
    seen = set()
    normalized_unique = [sid for sid in normalized if not (sid in seen or seen.add(sid))]

    mem.manage_schema_ids = normalized_unique
    db.commit()
    return {"ok": True, "message": "Permissions updated", "count": len(normalized_unique)}

