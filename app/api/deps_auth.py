from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import Optional, List
from uuid import UUID
import jwt

from app.api.deps import get_db
from app.core.config import settings
from app.core.security import decode_jwt
from app.models.auth_models import User, Account, Membership, Role

def get_authorization_header(authorization: Optional[str] = Header(default=None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing or invalid Authorization header")
    return authorization.split(" ", 1)[1].strip()

def current_user(db: Session = Depends(get_db), token: str = Depends(get_authorization_header)) -> User:
    try:
        payload = decode_jwt(token)
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid token")
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(401, "Invalid token")
    user = db.get(User, UUID(sub))
    if not user or not user.is_active:
        raise HTTPException(401, "Inactive user")
    return user

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
