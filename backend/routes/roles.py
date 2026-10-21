from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from database import get_db
from models import DigitalRole, DigitalWorker, Duty, RoleStatus, now_utc, gen_uuid
from schemas import RoleCreate, RoleUpdate, RoleResponse, PaginatedResponse
from deps import require_admin, get_current_user
from models import HumanUser
from services.spec_builder import role_task_types

router = APIRouter(prefix="/api/v1/roles", tags=["roles"])


def _role_dict(db: Session, role: DigitalRole) -> dict:
    duty_ids = role.duty_ids or []
    duty_names = []
    for did in duty_ids:
        d = db.query(Duty).filter(Duty.duty_id == did).first()
        if d:
            duty_names.append(d.name)
    return {
        "role_id": role.role_id,
        "name": role.name,
        "description": role.description or "",
        "duty_scope": role.duty_scope or [],
        "out_of_scope": role.out_of_scope or [],
        "duty_ids": duty_ids,
        "duty_names": duty_names,
        "task_types": role_task_types(db, role),
        "governance": role.governance or {},
        "version": role.version,
        "status": role.status.value if hasattr(role.status, "value") else role.status,
        "created_at": role.created_at,
        "updated_at": role.updated_at,
    }


def _validate_duty_ids(db: Session, duty_ids: list):
    if not duty_ids:
        raise HTTPException(status_code=400, detail="角色至少关联一个职责")
    for did in duty_ids:
        duty = db.query(Duty).filter(Duty.duty_id == did).first()
        if not duty:
            raise HTTPException(status_code=400, detail=f"职责不存在: {did}")
        if (duty.status.value if hasattr(duty.status, "value") else duty.status) != "ACTIVE":
            raise HTTPException(status_code=400, detail=f"职责已停用: {duty.name}")


@router.get("", response_model=PaginatedResponse)
def list_roles(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: HumanUser = Depends(get_current_user),
):
    q = db.query(DigitalRole)
    if status:
        q = q.filter(DigitalRole.status == status)
    total = q.count()
    items = q.order_by(DigitalRole.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return PaginatedResponse(total=total, page=page, page_size=page_size, items=[_role_dict(db, r) for r in items])


@router.post("", response_model=RoleResponse, status_code=201)
def create_role(
    data: RoleCreate,
    db: Session = Depends(get_db),
    user: HumanUser = Depends(require_admin),
):
    if db.query(DigitalRole).filter(DigitalRole.name == data.name).first():
        raise HTTPException(status_code=400, detail="角色名已存在")
    _validate_duty_ids(db, data.duty_ids)
    role = DigitalRole(
        role_id=gen_uuid(),
        name=data.name,
        description=data.description,
        duty_scope=data.duty_scope or [],
        out_of_scope=data.out_of_scope or [],
        duty_ids=data.duty_ids,
        governance=data.governance or {
            "autonomy_level": "L2",
            "token_budget_per_task": 100000,
            "max_concurrent_tasks": 5,
        },
        version=1,
        status=RoleStatus.ACTIVE,
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    return _role_dict(db, role)


@router.get("/{role_id}")
def get_role(role_id: str, db: Session = Depends(get_db), user: HumanUser = Depends(get_current_user)):
    role = db.query(DigitalRole).filter(DigitalRole.role_id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    return _role_dict(db, role)


@router.put("/{role_id}")
def update_role(
    role_id: str,
    data: RoleUpdate,
    db: Session = Depends(get_db),
    user: HumanUser = Depends(require_admin),
):
    role = db.query(DigitalRole).filter(DigitalRole.role_id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    payload = data.model_dump(exclude_unset=True)
    if "duty_ids" in payload:
        _validate_duty_ids(db, payload["duty_ids"] or [])
    for k, v in payload.items():
        if k == "status" and v:
            role.status = RoleStatus(v)
        else:
            setattr(role, k, v)
    role.version = (role.version or 1) + 1
    role.updated_at = now_utc()
    db.commit()
    db.refresh(role)
    return _role_dict(db, role)


@router.delete("/{role_id}", status_code=204)
def delete_role(
    role_id: str,
    db: Session = Depends(get_db),
    user: HumanUser = Depends(require_admin),
):
    role = db.query(DigitalRole).filter(DigitalRole.role_id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    worker_count = db.query(DigitalWorker).filter(DigitalWorker.role_id == role_id).count()
    if worker_count:
        raise HTTPException(
            status_code=400,
            detail=f"仍有 {worker_count} 个数字员工使用该角色，请先调整员工角色后再删除",
        )

    db.delete(role)
    db.commit()
    return None


@router.get("/{role_id}/workers")
def list_role_workers(role_id: str, db: Session = Depends(get_db), user: HumanUser = Depends(get_current_user)):
    workers = db.query(DigitalWorker).filter(DigitalWorker.role_id == role_id).all()
    from services.worker_service import _worker_response_fields
    return [_worker_response_fields(db, w) for w in workers]
