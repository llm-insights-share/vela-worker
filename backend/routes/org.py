from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Department, HumanUser, UserRole, gen_uuid
from schemas import DepartmentCreate, DepartmentResponse, HumanUserCreate
from deps import get_current_user, require_admin, require_platform_admin
from security import hash_password
from routes.auth import user_out, _validate_credentials, _ensure_unique

router = APIRouter(prefix="/api/v1/org", tags=["org"])


@router.get("/departments")
def list_departments(db: Session = Depends(get_db), user: HumanUser = Depends(get_current_user)):
    depts = db.query(Department).order_by(Department.sort).all()
    return [DepartmentResponse.model_validate(d) for d in depts]


@router.post("/departments", status_code=201)
def create_department(
    data: DepartmentCreate,
    db: Session = Depends(get_db),
    user: HumanUser = Depends(require_admin),
):
    d = Department(dept_id=gen_uuid(), name=data.name, parent_id=data.parent_id, sort=data.sort)
    db.add(d)
    db.commit()
    db.refresh(d)
    return DepartmentResponse.model_validate(d)


@router.get("/users")
def list_users(db: Session = Depends(get_db), user: HumanUser = Depends(get_current_user)):
    users = db.query(HumanUser).order_by(HumanUser.created_at).all()
    return [
        {
            "user_id": u.user_id,
            "name": u.name,
            "avatar": u.avatar or "",
            "dept_id": u.dept_id,
            "title": u.title or "",
            "role": u.role.value if hasattr(u.role, "value") else u.role,
            "status": u.status,
            "username": u.username or "",
            "email": u.email or "",
            "created_at": u.created_at,
        }
        for u in users
    ]


@router.get("/me")
def get_me(user: HumanUser = Depends(get_current_user)):
    return user_out(user)


@router.post("/users", status_code=201)
def create_user(
    data: HumanUserCreate,
    db: Session = Depends(get_db),
    user: HumanUser = Depends(require_platform_admin),
):
    """Deprecated: prefer POST /api/v1/users. Requires username/email/password."""
    if not data.username or not data.email or not data.password:
        raise HTTPException(
            status_code=400,
            detail="请使用 /api/v1/users 创建用户，并提供 username、email、password",
        )
    email, username = _validate_credentials(data.email, data.username, data.password)
    _ensure_unique(db, email=email, username=username)
    u = HumanUser(
        user_id=gen_uuid(),
        username=username,
        email=email,
        hashed_password=hash_password(data.password),
        name=data.name,
        avatar=data.avatar,
        dept_id=data.dept_id,
        title=data.title,
        role=UserRole(data.role) if data.role else UserRole.EMPLOYEE,
        status="ACTIVE",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return user_out(u)
