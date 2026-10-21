from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Department, HumanUser, DigitalWorker, UserRole, gen_uuid
from schemas import DepartmentCreate, DepartmentUpdate, DepartmentResponse, HumanUserCreate
from deps import get_current_user, require_admin, require_platform_admin
from security import hash_password
from routes.auth import user_out, _validate_credentials, _ensure_unique

router = APIRouter(prefix="/api/v1/org", tags=["org"])


def _get_dept(db: Session, dept_id: str) -> Department:
    dept = db.query(Department).filter(Department.dept_id == dept_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="部门不存在")
    return dept


def _validate_parent(db: Session, parent_id: str | None, self_id: str | None = None):
    if not parent_id:
        return
    if self_id and parent_id == self_id:
        raise HTTPException(status_code=400, detail="上级部门不能是自身")
    parent = db.query(Department).filter(Department.dept_id == parent_id).first()
    if not parent:
        raise HTTPException(status_code=400, detail="上级部门不存在")
    # Prevent cycles: walk up from parent
    if self_id:
        cursor = parent
        seen = {self_id}
        while cursor:
            if cursor.dept_id in seen:
                raise HTTPException(status_code=400, detail="上级部门不能形成循环")
            seen.add(cursor.dept_id)
            if not cursor.parent_id:
                break
            cursor = db.query(Department).filter(Department.dept_id == cursor.parent_id).first()


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
    _validate_parent(db, data.parent_id)
    d = Department(dept_id=gen_uuid(), name=data.name, parent_id=data.parent_id, sort=data.sort)
    db.add(d)
    db.commit()
    db.refresh(d)
    return DepartmentResponse.model_validate(d)


@router.put("/departments/{dept_id}")
def update_department(
    dept_id: str,
    data: DepartmentUpdate,
    db: Session = Depends(get_db),
    user: HumanUser = Depends(require_admin),
):
    dept = _get_dept(db, dept_id)
    payload = data.model_dump(exclude_unset=True)
    if "parent_id" in payload:
        _validate_parent(db, payload.get("parent_id"), self_id=dept_id)
    for k, v in payload.items():
        setattr(dept, k, v)
    db.commit()
    db.refresh(dept)
    return DepartmentResponse.model_validate(dept)


@router.delete("/departments/{dept_id}", status_code=204)
def delete_department(
    dept_id: str,
    db: Session = Depends(get_db),
    user: HumanUser = Depends(require_admin),
):
    dept = _get_dept(db, dept_id)
    child_count = db.query(Department).filter(Department.parent_id == dept_id).count()
    if child_count:
        raise HTTPException(
            status_code=400,
            detail=f"仍有 {child_count} 个子部门，请先删除或调整子部门后再删除",
        )
    user_count = db.query(HumanUser).filter(HumanUser.dept_id == dept_id).count()
    if user_count:
        raise HTTPException(
            status_code=400,
            detail=f"仍有 {user_count} 名用户归属该部门，请先调整后再删除",
        )
    worker_count = db.query(DigitalWorker).filter(DigitalWorker.dept_id == dept_id).count()
    if worker_count:
        raise HTTPException(
            status_code=400,
            detail=f"仍有 {worker_count} 个数字员工归属该部门，请先调整后再删除",
        )
    db.delete(dept)
    db.commit()
    return None


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
