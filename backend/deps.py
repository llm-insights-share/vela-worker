"""Auth helpers — JWT Bearer (aligned with vela-agent)."""
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from database import get_db
from models import HumanUser, UserRole
from security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

DbDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[str, Depends(oauth2_scheme)]


def get_current_user(db: DbDep, token: TokenDep) -> HumanUser:
    try:
        payload = decode_token(token)
        username = payload.get("sub")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(HumanUser).filter(HumanUser.username == username).first()
    if not user or user.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User inactive or missing",
        )
    return user


CurrentUser = Annotated[HumanUser, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> HumanUser:
    if user.role not in (UserRole.PLATFORM_ADMIN, UserRole.DEPT_ADMIN):
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


def require_platform_admin(user: CurrentUser) -> HumanUser:
    if user.role != UserRole.PLATFORM_ADMIN:
        raise HTTPException(status_code=403, detail="需要平台管理员权限")
    return user


AdminUser = Annotated[HumanUser, Depends(require_admin)]
PlatformAdminUser = Annotated[HumanUser, Depends(require_platform_admin)]
