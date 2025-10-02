from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import Optional, List
from uuid import UUID
import jwt

from app.api.deps import get_db
from app.core.config import settings
from app.core.security import decode_jwt
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.models.auth_models import User, Account, Membership, Role

def get_authorization_header(authorization: Optional[str] = Header(default=None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing or invalid Authorization header")
    return authorization.split(" ", 1)[1].strip()

bearer = HTTPBearer(auto_error=False)
def current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if not creds or creds.scheme.lower() != "bearer":
        # Missing header or wrong scheme
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    try:
        payload = decode_jwt(creds.credentials)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        if not (user.is_active and user.email_verified_at):
            # Block unverified/inactive users explicitly
            raise HTTPException(status_code=403, detail="User is not active or not verified")

        return user
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

def current_account_id(token: str = Depends(get_authorization_header)) -> UUID:
    payload = decode_jwt(token)
    aid = payload.get("aid")
    if not aid:
        raise HTTPException(401, "No account in token")
    return UUID(aid)

def require_role(allowed: List[Role]):
    def _dep(
        db: Session = Depends(get_db),
        user: User = Depends(current_user),
        account_id: UUID = Depends(current_account_id),
    ) -> Membership:
        mem = (
            db.query(Membership)
            .filter(Membership.account_id == account_id, Membership.user_id == user.id)
            .first()
        )
        if not mem or mem.role not in allowed:
            raise HTTPException(403, "Insufficient permissions")
        return mem
    return _dep
