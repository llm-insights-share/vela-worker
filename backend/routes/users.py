from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from deps import PlatformAdminUser
from models import HumanUser, UserRole, gen_uuid, now_utc
from schemas import ActiveIn, AdminCreateUserIn, RolesIn, UserOut
from security import hash_password
from routes import auth as auth_helpers

router = APIRouter(prefix="/api/v1/users", tags=["users"])

VALID_ROLES = {r.value for r in UserRole}


def _count_active_platform_admins(db: Session, *, exclude_id: str | None = None) -> int:
    n = 0
    for u in db.query(HumanUser).filter(HumanUser.status == "ACTIVE").all():
        if exclude_id is not None and u.user_id == exclude_id:
            continue
        role = u.role.value if hasattr(u.role, "value") else u.role
        if role == UserRole.PLATFORM_ADMIN.value:
            n += 1
    return n


def _parse_role(role: str) -> UserRole:
    r = (role or "EMPLOYEE").strip().upper()
    if r not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"无效角色: {role}")
    return UserRole(r)


@router.get("", response_model=List[UserOut])
def list_users(_admin: PlatformAdminUser, db: Session = Depends(get_db)):
    rows = db.query(HumanUser).order_by(HumanUser.created_at.asc()).all()
    return [auth_helpers.user_out(u) for u in rows]


@router.post("", response_model=UserOut)
def create_user(body: AdminCreateUserIn, _admin: PlatformAdminUser, db: Session = Depends(get_db)):
    email, username = auth_helpers._validate_credentials(body.email, body.username, body.password)
    auth_helpers._ensure_unique(db, email=email, username=username)
    role = _parse_role(body.role)
    display = (body.display_name or "").strip() or username
    user = HumanUser(
        user_id=gen_uuid(),
        username=username,
        email=email,
        name=display,
        hashed_password=hash_password(body.password),
        role=role,
        dept_id=body.dept_id,
        title=(body.title or "").strip(),
        status="ACTIVE",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return auth_helpers.user_out(user)


@router.patch("/{user_id}/active", response_model=UserOut)
def set_user_active(
    user_id: str,
    body: ActiveIn,
    admin: PlatformAdminUser,
    db: Session = Depends(get_db),
):
    user = db.query(HumanUser).filter(HumanUser.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.user_id == admin.user_id:
        raise HTTPException(status_code=400, detail="Cannot block yourself")
    role = user.role.value if hasattr(user.role, "value") else user.role
    if not body.is_active and role == UserRole.PLATFORM_ADMIN.value:
        if _count_active_platform_admins(db, exclude_id=user.user_id) < 1:
            raise HTTPException(status_code=400, detail="Cannot block the last platform admin")
    user.status = "ACTIVE" if body.is_active else "DISABLED"
    user.updated_at = now_utc()
    db.add(user)
    db.commit()
    db.refresh(user)
    return auth_helpers.user_out(user)


@router.patch("/{user_id}/roles", response_model=UserOut)
def set_user_roles(
    user_id: str,
    body: RolesIn,
    admin: PlatformAdminUser,
    db: Session = Depends(get_db),
):
    user = db.query(HumanUser).filter(HumanUser.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    next_role = _parse_role(body.role)
    curr = user.role.value if hasattr(user.role, "value") else user.role
    if next_role != UserRole.PLATFORM_ADMIN and curr == UserRole.PLATFORM_ADMIN.value:
        if user.status == "ACTIVE" and _count_active_platform_admins(db, exclude_id=user.user_id) < 1:
            raise HTTPException(status_code=400, detail="Cannot remove the last platform admin")
    user.role = next_role
    user.updated_at = now_utc()
    db.add(user)
    db.commit()
    db.refresh(user)
    return auth_helpers.user_out(user)


@router.delete("/{user_id}")
def delete_user(user_id: str, admin: PlatformAdminUser, db: Session = Depends(get_db)):
    user = db.query(HumanUser).filter(HumanUser.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.user_id == admin.user_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    role = user.role.value if hasattr(user.role, "value") else user.role
    if role == UserRole.PLATFORM_ADMIN.value and user.status == "ACTIVE":
        if _count_active_platform_admins(db, exclude_id=user.user_id) < 1:
            raise HTTPException(status_code=400, detail="Cannot delete the last platform admin")
    db.delete(user)
    db.commit()
    return {"ok": True}
