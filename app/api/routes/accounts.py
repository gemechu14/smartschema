from datetime import timedelta
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.deps_auth import require_role_for_account  # <-- new dep (path-only)
from app.core.config import settings
from app.core.security import random_token, sha256, now_utc
from app.models.auth_models import Account, Membership, Role, User, Invitation
from app.models.schema_spec import SchemaSpecification
from app.schemas.auth import (
    InviteMemberBody,
    MemberOut,
    AccountRename,
    MemberUpdatePermissions,
    TeamMemberOut,
)
from app.schemas.auth import MemberUpdatePermissions as _MemberUpdatePermissions
from typing import Optional
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





@router.get(
    "/{account_id}/team_members",
    response_model=list[TeamMemberOut],
    summary="List team members and pending invites (Owner/Admin)",
    description="Returns active members (ADMIN/MEMBER) and pending invites with status and schema access.",
)
def team_members(
    account_id: UUID,
    tup = Depends(require_role_for_account({Role.OWNER, Role.ADMIN})),
    db: Session = Depends(get_db),
):
    # members: include ADMIN and MEMBER roles only, but exclude the caller
    caller_user = tup[0]
    rows = (
        db.query(Membership, User)
        .join(User, User.id == Membership.user_id)
        .filter(
            Membership.account_id == account_id,
            Membership.role.in_([Role.ADMIN, Role.MEMBER]),
            Membership.user_id != caller_user.id,
        )
        .all()
    )

    members = [
        {
            "user_id": str(u.id),
            "email": u.email,
            "role": m.role.value.lower(),
            "schema_access": m.manage_schema_ids or [],
            "status": "active" if u.is_active else "inactive",
        }
        for (m, u) in rows
    ]

    # pending invites (not accepted) - map to same shape, status pending/expired
    from app.models.verification import EmailVerification
    invites = (
        db.query(Invitation)
        .filter(Invitation.account_id == account_id)
        .all()
    )
    from app.core.security import ensure_aware, now_utc
    now = now_utc()
    for inv in invites:
        if inv.accepted_at:
            # if accepted and there is a membership, skip; otherwise show as active if user exists
            continue
        status = "pending"
        try:
            if ensure_aware(inv.expires_at) < now:
                status = "expired"
        except Exception:
            # If expires_at is malformed or comparison fails, conservatively keep pending
            status = "pending"
        members.append({
            "user_id": None,
            "email": inv.email,
            "role": inv.role.value.lower(),
            "schema_access": inv.manage_schema_ids or [],
            "status": status,
        })

    # Return only members and admins (already filtered)
    return members





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

    # Prevent inviting someone who's already an active member or already has a pending invite
    email_norm = str(body.email).lower().strip()
    existing_member = (
        db.query(Membership)
        .join(User, User.id == Membership.user_id)
        .filter(Membership.account_id == account_id, User.email == email_norm)
        .first()
    )
    if existing_member:
        raise HTTPException(400, detail="User is already a member of this account")

    existing_invite = (
        db.query(Invitation)
        .filter(Invitation.account_id == account_id, Invitation.email == email_norm, Invitation.accepted_at == None)
        .first()
    )
    if existing_invite:
        raise HTTPException(400, detail="There is already a pending invitation for this email")

    # --- create invite ---
    raw = random_token(32)
    inv = Invitation(
        account_id=account_id,
        email=email_norm,
        role=Role(body.role),
        token_hash=sha256(raw),
        expires_at=now_utc() + timedelta(days=settings.invite_exp_days),
        manage_schema_ids=normalized_unique or None,  # <- JSON-serializable
    )
    db.add(inv)
    db.commit()

    # email
    link = f"{settings.app_base_url}/auth/signup?invite={raw}&email={inv.email}"
    # Build a styled invite email similar to other transactional emails
    inviter_user = tup[0]
    account = db.get(Account, account_id)
    expiry_days = settings.invite_exp_days
    # human readable role label (e.g. 'Member', 'Admin')
    role_label = (inv.role.value.replace('_', ' ').title() if hasattr(inv, 'role') else str(inv.role))
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>You're invited to {settings.app_name}</title>
    <style>
        body {{ font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f6f8fb; margin: 0; padding: 0; color: #333; }}
        .container {{ max-width: 600px; margin: 40px auto; background-color: #fff; border-radius: 12px; box-shadow: 0 4px 8px rgba(0,0,0,0.05); overflow: hidden; }}
        .header {{ background-color: #0f172a; color: #fff; text-align: center; padding: 28px 24px; }}
        .content {{ padding: 28px 32px; line-height: 1.6; }}
        .btn {{ display:inline-block; background:#0f172a; color:#ffffff !important; -webkit-text-size-adjust:none; padding:12px 20px; border-radius:8px; text-decoration:none }}
        .footer {{ text-align: center; color: #999; font-size: 12px; padding: 16px 0; }}
        h1 {{ margin: 0; font-size: 22px; }}
        h3 {{ margin-top: 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Welcome to {settings.app_name}</h1>
        </div>
        <div class="content">
            <h3>Hello,</h3>
            <p><strong>{inviter_user.first_name or inviter_user.email}</strong> has invited you to join the workspace <strong>{account.name}</strong> as <strong>{role_label}</strong>.</p>
            <p>To accept the invitation and create your account, click the button below:</p>
            <p style="text-align:left;"><a class="btn" href="{link}" style="color:#ffffff !important; text-decoration:none;">Accept Invitation</a></p>
            <p>This invitation will expire in <strong>{expiry_days} days</strong>. If the button doesn't work, copy and paste this URL into your browser:<br><a href="{link}">{link}</a></p>
            <p>If you did not expect this invitation, you can ignore this message.</p>
            <p>Cheers,<br>The {settings.app_name} Team</p>
        </div>
        <div class="footer">
            &copy; {__import__('datetime').datetime.utcnow().year} {settings.app_name}. All rights reserved.
        </div>
    </div>
</body>
</html>
'''
    try:
        send_email(to_email=inv.email, subject=f"You're invited to {settings.app_name}", html=html, from_name=settings.mail_from_name)
    except Exception:
        # best-effort: don't fail invite creation if email sending fails
        pass

    return {"ok": True, "message": "Invitation created (email sent if SMTP available)."}


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


# (Path-based permissions endpoint removed — use the body-only
# `PUT /{account_id}/members/permissions` endpoint instead.)


# New body-only endpoint to update member permissions without a path user id
@router.put(
    "/{account_id}/members/permissions",
    summary="Update member or invite permissions by body (Owner/Admin)",
    description="""
Replace per-schema management for a member or update pending invite(s) by email. If `user_id` is provided in the body, it behaves like the path-based endpoint. If `email` is provided and `user_id` is omitted, only invitations matching that email will be updated.
""",
)
def update_member_permissions_by_body(
    account_id: UUID,
    body: MemberUpdatePermissions,
    tup = Depends(require_role_for_account({Role.OWNER, Role.ADMIN})),
    db: Session = Depends(get_db),
):
    # Determine target: prefer user_id, else email
    caller_user, _aid, caller_role = tup

    if body.user_id is not None:
        target_user_id = body.user_id
        # try membership first
        mem = (
            db.query(Membership)
            .filter(Membership.account_id == account_id, Membership.user_id == target_user_id)
            .first()
        )
        if mem:
            # Role update logic for membership (if provided)
            if body.role is not None:
                # Normalize incoming role to string (e.g. RoleEnum or raw string)
                role_str = body.role.value if hasattr(body.role, 'value') else str(body.role)
                # Disallow promoting to OWNER via this API
                if role_str == Role.OWNER.value:
                    raise HTTPException(status_code=403, detail="Promoting a member to OWNER is not allowed")
                # Admin callers cannot change Owner roles
                if caller_role == Role.ADMIN and mem.role == Role.OWNER:
                    raise HTTPException(status_code=403, detail="Admins may not change Owner roles")
                # prevent removing last OWNER (if demoting caller)
                if role_str != Role.OWNER.value:
                    owners = (
                        db.query(Membership)
                        .filter(Membership.account_id == account_id, Membership.role == Role.OWNER)
                        .count()
                    )
                    if owners <= 1 and target_user_id == caller_user.id:
                        raise HTTPException(400, "Cannot demote the last OWNER")
                # apply role (convert string -> Role)
                try:
                    mem.role = Role(role_str)
                    # If promoted to ADMIN/OWNER, clear per-schema manage list
                    if mem.role in (Role.ADMIN, Role.OWNER):
                        mem.manage_schema_ids = None
                        # Also clear any pending invites for this user in this account
                        try:
                            # fetch user's email if membership has user_id
                            if mem.user_id:
                                u = db.get(User, mem.user_id)
                                if u:
                                    invites = db.query(Invitation).filter(Invitation.account_id == account_id, Invitation.email == u.email).all()
                                    for inv in invites:
                                        inv.manage_schema_ids = None
                        except Exception:
                            # best-effort: don't fail the role change if invite cleanup fails
                            pass
                except Exception:
                    pass

            # Only process manage_schema_ids when the field was provided in the request
            if body.manage_schema_ids is not None:
                raw_ids = body.manage_schema_ids
                normalized: list[str] = []
                for x in raw_ids:
                    try:
                        normalized.append(str(UUID(str(x))))
                    except Exception:
                        raise HTTPException(400, detail=f"Invalid schema id: {x}")

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

                seen = set()
                normalized_unique = [sid for sid in normalized if not (sid in seen or seen.add(sid))]

                # Only assign per-schema manage list to MEMBER or VIEWER roles.
                if mem.role in (Role.MEMBER, getattr(Role, 'VIEWER', None)):
                    mem.manage_schema_ids = normalized_unique or None
                else:
                    # For ADMIN/OWNER, clear per-schema manage list
                    mem.manage_schema_ids = None

            db.commit()
            return {"ok": True, "message": "Permissions updated"}

        # no membership -> update invites for the user (require user exists)
        from app.models.auth_models import User as _User
        user = db.query(_User).filter(_User.id == target_user_id).first()
        if not user:
            raise HTTPException(404, "No membership and no user found for provided user_id")

        invite_targets = (
            db.query(Invitation)
            .filter(Invitation.account_id == account_id, Invitation.email == user.email)
            .all()
        )
        if not invite_targets:
            raise HTTPException(404, "No pending invites found for this user")
        # If a role is provided, apply to invites as well (but disallow OWNER)
        role_str = None
        if body.role is not None:
            role_str = body.role.value if hasattr(body.role, 'value') else str(body.role)
            if role_str == Role.OWNER.value:
                raise HTTPException(status_code=403, detail="Promoting to OWNER is not allowed via this API")
            # Apply role to invites and clear per-schema list if promoted to ADMIN/OWNER
            for inv in invite_targets:
                try:
                    inv.role = Role(role_str)
                    if role_str in (Role.ADMIN.value, Role.OWNER.value):
                        inv.manage_schema_ids = None
                except Exception:
                    pass

        raw_ids = body.manage_schema_ids or []
        normalized: list[str] = []
        for x in raw_ids:
            try:
                normalized.append(str(UUID(str(x))))
            except Exception:
                raise HTTPException(400, detail=f"Invalid schema id: {x}")

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

        seen = set()
        normalized_unique = [sid for sid in normalized if not (sid in seen or seen.add(sid))]
        for inv in invite_targets:
            # If role was set to ADMIN/OWNER above, ensure we don't apply per-schema ids
            if role_str and role_str in (Role.ADMIN.value, Role.OWNER.value):
                inv.manage_schema_ids = None
            else:
                inv.manage_schema_ids = normalized_unique or None
        db.commit()
        return {"ok": True, "message": "Invite(s) updated", "count": len(invite_targets)}

    # else email provided
    if body.email is not None:
        email = body.email.lower().strip()
        # Prefer updating an existing membership for that email if present
        from app.models.auth_models import User as _User
        user = db.query(_User).filter(_User.email == email).first()
        if user:
            mem = (
                db.query(Membership)
                .filter(Membership.account_id == account_id, Membership.user_id == user.id)
                .first()
            )
            if mem:
                # If role provided, apply to membership with same safeguards as above
                if body.role is not None:
                    role_str = body.role.value if hasattr(body.role, 'value') else str(body.role)
                    if role_str == Role.OWNER.value:
                        raise HTTPException(status_code=403, detail="Promoting a member to OWNER is not allowed")
                    if caller_role == Role.ADMIN and mem.role == Role.OWNER:
                        raise HTTPException(status_code=403, detail="Admins may not change Owner roles")
                    if role_str != Role.OWNER.value:
                        owners = (
                            db.query(Membership)
                            .filter(Membership.account_id == account_id, Membership.role == Role.OWNER)
                            .count()
                        )
                        if owners <= 1 and user.id == caller_user.id:
                            raise HTTPException(400, "Cannot demote the last OWNER")
                    try:
                        mem.role = Role(role_str)
                        # If promoted to ADMIN/OWNER, clear per-schema manage list
                        if mem.role in (Role.ADMIN, Role.OWNER):
                            mem.manage_schema_ids = None
                            # Also clear pending invites matching this user's email
                            try:
                                if user:
                                    invites = db.query(Invitation).filter(Invitation.account_id == account_id, Invitation.email == user.email).all()
                                    for inv in invites:
                                        inv.manage_schema_ids = None
                            except Exception:
                                pass
                    except Exception:
                        pass

                # manage_schema_ids only if provided
                if body.manage_schema_ids is not None:
                    raw_ids = body.manage_schema_ids
                    normalized: list[str] = []
                    for x in raw_ids:
                        try:
                            normalized.append(str(UUID(str(x))))
                        except Exception:
                            raise HTTPException(400, detail=f"Invalid schema id: {x}")

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

                    seen = set()
                    normalized_unique = [sid for sid in normalized if not (sid in seen or seen.add(sid))]

                    if mem.role in (Role.MEMBER, getattr(Role, 'VIEWER', None)):
                        mem.manage_schema_ids = normalized_unique or None
                    else:
                        mem.manage_schema_ids = None

                db.commit()
                return {"ok": True, "message": "Membership updated by email"}

        # No active membership -> update invites matching this email
        invite_targets = (
            db.query(Invitation)
            .filter(Invitation.account_id == account_id, Invitation.email == email)
            .all()
        )
        if not invite_targets:
            raise HTTPException(404, "No pending invites found for this email")

        # Optionally apply role to invites
        role_str = None
        if body.role is not None:
            role_str = body.role.value if hasattr(body.role, 'value') else str(body.role)
            if role_str == Role.OWNER.value:
                raise HTTPException(status_code=403, detail="Promoting to OWNER is not allowed via this API")
            for inv in invite_targets:
                try:
                    inv.role = Role(role_str)
                    if role_str in (Role.ADMIN.value, Role.OWNER.value):
                        inv.manage_schema_ids = None
                except Exception:
                    pass

        # manage_schema_ids for invites only if provided
        if body.manage_schema_ids is not None:
            raw_ids = body.manage_schema_ids
            normalized: list[str] = []
            for x in raw_ids:
                try:
                    normalized.append(str(UUID(str(x))))
                except Exception:
                    raise HTTPException(400, detail=f"Invalid schema id: {x}")

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

            seen = set()
            normalized_unique = [sid for sid in normalized if not (sid in seen or seen.add(sid))]
            for inv in invite_targets:
                if role_str and role_str in (Role.ADMIN.value, Role.OWNER.value):
                    inv.manage_schema_ids = None
                else:
                    inv.manage_schema_ids = normalized_unique or None
        db.commit()
        return {"ok": True, "message": "Invite(s) updated by email", "count": len(invite_targets)}

    raise HTTPException(400, "Either user_id or email must be provided in request body")

