from typing import Iterable, Tuple
from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.security import decode_jwt
from app.models.auth_models import User, Membership, Role


bearer = HTTPBearer(auto_error=False)


def current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    """
    Authenticate with Bearer access token and return the User.
    Blocks inactive or unverified users.
    """
    if not creds or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    try:
        payload = decode_jwt(creds.credentials)
        uid = payload.get("sub")
        if not uid:
            raise HTTPException(status_code=401, detail="Invalid token payload")

        user = db.query(User).filter(User.id == uid).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        if not user.is_active or not user.email_verified_at:
            raise HTTPException(status_code=403, detail="User is not active or not verified")
        return user

    except HTTPException:
        raise
    except Exception:
        # invalid signature, expired, malformed, etc.
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def require_role_for_account(allowed: Iterable[Role]):
    """
    Path-only authorization helper.

    Usage in routes that have `account_id` in the path:
        tup = Depends(require_role_for_account({Role.OWNER, Role.ADMIN}))

    Returns a tuple (user, account_id, role) if allowed, otherwise raises 403.
    """
    def dep(
        account_id: UUID,
        user: User = Depends(current_user),
        db: Session = Depends(get_db),
    ) -> Tuple[User, UUID, Role]:
        mem = (
            db.query(Membership)
            .filter(Membership.account_id == account_id, Membership.user_id == user.id)
            .first()
        )
        if not mem:
            raise HTTPException(status_code=403, detail="Not a member of this account")
        if mem.role not in allowed:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return (user, account_id, mem.role)

    return dep
