from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from database import get_db
from models import DigitalWorker, HumanUser, UserRole
from schemas import (
    WorkerCreate, WorkerUpdate, PermissionOverrideRequest, WorkerDutyAddRequest, PaginatedResponse,
)
from deps import get_current_user, require_admin
from services import worker_service
from services.spec_builder import build_worker_spec, worker_task_types

router = APIRouter(prefix="/api/v1/workers", tags=["workers"])


@router.get("", response_model=PaginatedResponse)
def list_workers(
    dept_id: Optional[str] = None,
    status: Optional[str] = None,
    task_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: HumanUser = Depends(get_current_user),
):
    q = db.query(DigitalWorker)
    if dept_id:
        q = q.filter(DigitalWorker.dept_id == dept_id)
    if status:
        q = q.filter(DigitalWorker.status == status)
    total = q.count()
    items = q.order_by(DigitalWorker.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    result = [worker_service._worker_response_fields(db, w) for w in items]
    if task_type:
        filtered = []
        for w, raw in zip(items, result):
            if task_type in worker_task_types(db, w):
                filtered.append(raw)
        return PaginatedResponse(total=len(filtered), page=page, page_size=page_size, items=filtered)
    return PaginatedResponse(total=total, page=page, page_size=page_size, items=result)


@router.post("", status_code=201)
def create_worker(
    data: WorkerCreate,
    db: Session = Depends(get_db),
    user: HumanUser = Depends(require_admin),
):
    worker = worker_service.onboard_worker(
        db,
        name=data.name,
        role_id=data.role_id,
        dept_id=data.dept_id,
        avatar=data.avatar,
        escalation_contact=data.escalation_contact,
        remark=data.remark,
        actor_id=user.user_id,
    )
    return worker_service._worker_response_fields(db, worker)


@router.get("/{worker_id}")
def get_worker(worker_id: str, db: Session = Depends(get_db), user: HumanUser = Depends(get_current_user)):
    worker = db.query(DigitalWorker).filter(DigitalWorker.worker_id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="数字员工不存在")
    return worker_service._worker_response_fields(db, worker)


@router.put("/{worker_id}")
def update_worker(
    worker_id: str,
    data: WorkerUpdate,
    db: Session = Depends(get_db),
    user: HumanUser = Depends(require_admin),
):
    worker = db.query(DigitalWorker).filter(DigitalWorker.worker_id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="数字员工不存在")
    payload = data.model_dump(exclude_unset=True)
    if "status" in payload and payload["status"]:
        return worker_service._worker_response_fields(
            db, worker_service.set_worker_status(db, worker_id, payload["status"], actor_id=user.user_id)
        )
    for k, v in payload.items():
        if k != "status":
            setattr(worker, k, v)
    db.commit()
    db.refresh(worker)
    return worker_service._worker_response_fields(db, worker)


@router.get("/{worker_id}/spec")
def get_worker_spec(worker_id: str, db: Session = Depends(get_db), user: HumanUser = Depends(get_current_user)):
    worker = db.query(DigitalWorker).filter(DigitalWorker.worker_id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="数字员工不存在")
    return build_worker_spec(db, worker)


@router.get("/{worker_id}/duties")
def list_worker_duties(worker_id: str, db: Session = Depends(get_db), user: HumanUser = Depends(get_current_user)):
    worker = db.query(DigitalWorker).filter(DigitalWorker.worker_id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="数字员工不存在")
    return worker_service._worker_response_fields(db, worker).get("duties", [])


@router.post("/{worker_id}/duties", status_code=201)
def add_worker_duty(
    worker_id: str,
    data: WorkerDutyAddRequest,
    db: Session = Depends(get_db),
    user: HumanUser = Depends(require_admin),
):
    worker = worker_service.add_worker_duty(
        db, worker_id, data.duty_id, is_primary=data.is_primary, actor_id=user.user_id,
    )
    return worker_service._worker_response_fields(db, worker)


@router.delete("/{worker_id}/duties/{duty_id}")
def remove_worker_duty(
    worker_id: str,
    duty_id: str,
    db: Session = Depends(get_db),
    user: HumanUser = Depends(require_admin),
):
    worker = worker_service.remove_worker_duty(db, worker_id, duty_id, actor_id=user.user_id)
    return worker_service._worker_response_fields(db, worker)


@router.post("/{worker_id}/repair-entry")
def repair_worker_entry(
    worker_id: str,
    db: Session = Depends(get_db),
    user: HumanUser = Depends(require_admin),
):
    """Rebuild COMPOSITE entry agent and remount duty sub-agents."""
    worker = worker_service.repair_worker_entry(db, worker_id, actor_id=user.user_id)
    return worker_service._worker_response_fields(db, worker)


@router.put("/{worker_id}/permissions")
def update_permissions(
    worker_id: str,
    data: PermissionOverrideRequest,
    db: Session = Depends(get_db),
    user: HumanUser = Depends(require_admin),
):
    is_platform = user.role == UserRole.PLATFORM_ADMIN
    worker = worker_service.apply_permission_overrides(
        db,
        worker_id,
        tool_overrides=data.tool_overrides if data.tool_overrides is not None else None,
        kb_overrides=data.kb_overrides or None,
        governance_overrides=data.governance_overrides or None,
        duty_scope_override=data.duty_scope_override,
        actor_id=user.user_id,
        is_platform_admin=is_platform,
    )
    return worker_service._worker_response_fields(db, worker)
