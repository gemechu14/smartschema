from datetime import timedelta
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.api.deps_auth import current_user, current_account_id, require_role
from app.core.config import settings
from app.core.security import random_token, sha256, now_utc
from app.models.auth_models import Account, Membership, Role, User, Invitation
from app.schemas.auth import InviteCreate, MemberOut, AccountRename
from app.services.mailer import send_email

router = APIRouter(prefix="/accounts", tags=["accounts"])

@router.get("/current")
def current_account(aid: UUID = Depends(current_account_id), db: Session = Depends(get_db)):
    acc = db.get(Account, aid)
    if not acc:
        raise HTTPException(404, "Account not found")
    return {"id": str(acc.id), "name": acc.name}

@router.get("/{account_id}/members", response_model=list[MemberOut])
def list_members(
    account_id: UUID,
    mem = Depends(require_role([Role.OWNER, Role.ADMIN])),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Membership, User)
        .join(User, User.id == Membership.user_id)
        .filter(Membership.account_id == account_id)
        .all()
    )
    out = []
    for m, u in rows:
        out.append(MemberOut(user_id=u.id, email=u.email, role=m.role, first_name=u.first_name, last_name=u.last_name))
    return out

@router.patch("/{account_id}/members/{user_id}")
def change_role(
    account_id: UUID,
    user_id: UUID,
    role: Role,
    mem = Depends(require_role([Role.OWNER, Role.ADMIN])),
    db: Session = Depends(get_db),
):
    # prevent removing last OWNER
    if role != Role.OWNER:
        owners = (
            db.query(Membership)
            .filter(Membership.account_id == account_id, Membership.role == Role.OWNER)
            .count()
        )
        if owners <= 1 and user_id == mem.user_id:
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

@router.delete("/{account_id}/members/{user_id}")
def remove_member(
    account_id: UUID,
    user_id: UUID,
    mem = Depends(require_role([Role.OWNER, Role.ADMIN])),
    db: Session = Depends(get_db),
):
    # block removing last OWNER
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
    db.delete(victim); db.commit()
    return {"ok": True}

@router.post("/{account_id}/invites")
def create_invite(
    account_id: UUID,
    body: InviteCreate,
    mem = Depends(require_role([Role.OWNER, Role.ADMIN])),
    db: Session = Depends(get_db),
):
    # create signed+stored token
    raw = random_token(24)
    token_hash = sha256(raw)
    inv = Invitation(
        account_id=account_id,
        email=body.email.lower().strip(),
        role=body.role,
        token_hash=token_hash,
        expires_at=now_utc() + timedelta(days=settings.invite_exp_days),
    )
    db.add(inv); db.commit()

    link = f"{settings.app_base_url}/signup?invite={raw}"
    html = f"""
    <p>You have been invited to join an account on Locimapper.</p>
    <p>Click to accept: <a href="{link}">{link}</a></p>
    """
    send_email(body.email, "Your Locimapper invite", html, from_name="Locimapper")
    return {"ok": True}

@router.get("/invites/{token}")
def preview_invite(token: str, db: Session = Depends(get_db)):
    inv = db.query(Invitation).filter(Invitation.token_hash == sha256(token)).first()
    if not inv or inv.expires_at < now_utc():
        raise HTTPException(404, "Invite not found or expired")
    return {"email": inv.email, "role": inv.role, "account_id": str(inv.account_id)}

@router.patch("/{account_id}")
def rename_account(
    account_id: UUID,
    body: AccountRename,
    mem = Depends(require_role([Role.OWNER])),  # only OWNER can rename
    db: Session = Depends(get_db),
):
    acc = db.get(Account, account_id)
    if not acc:
        raise HTTPException(404, "Account not found")
    acc.name = body.name.strip()
    db.commit()
    return {"ok": True, "id": str(acc.id), "name": acc.name}
