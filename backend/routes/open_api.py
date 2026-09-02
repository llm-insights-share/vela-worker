import hashlib
import secrets
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from database import get_db
from models import OpenApp, DigitalWorker, DigitalRole, WorkTask, WorkerStatus, TaskSource, HumanUser, gen_uuid
from schemas import OpenAppCreate, TaskCreate, PaginatedResponse
from deps import require_platform_admin, get_current_user
from services.task_runner import create_and_start_task, cancel_task, schedule_task
from services.spec_builder import build_worker_spec, worker_task_types

apps_router = APIRouter(prefix="/api/v1/apps", tags=["apps"])
open_router = APIRouter(prefix="/api/v1/open", tags=["open-api"])


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


@apps_router.get("")
def list_apps(db: Session = Depends(get_db), user: HumanUser = Depends(require_platform_admin)):
    apps = db.query(OpenApp).order_by(OpenApp.created_at.desc()).all()
    return [
        {
            "app_id": a.app_id,
            "name": a.name,
            "api_key": a.api_key,
            "allowed_task_types": a.allowed_task_types or [],
            "default_callback_url": a.default_callback_url or "",
            "status": a.status,
            "created_at": a.created_at,
        }
        for a in apps
    ]


@apps_router.post("", status_code=201)
def create_app(
    data: OpenAppCreate,
    db: Session = Depends(get_db),
    user: HumanUser = Depends(require_platform_admin),
):
    api_key = "vw_" + secrets.token_hex(16)
    app_secret = secrets.token_hex(24)
    app = OpenApp(
        app_id=gen_uuid(),
        name=data.name,
        api_key=api_key,
        api_key_hash=_hash(api_key),
        app_secret=app_secret,
        app_secret_hash=_hash(app_secret),
        allowed_task_types=data.allowed_task_types,
        default_callback_url=data.default_callback_url,
        status="ACTIVE",
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return {
        "app_id": app.app_id,
        "name": app.name,
        "api_key": api_key,
        "app_secret": app_secret,
        "allowed_task_types": app.allowed_task_types or [],
        "default_callback_url": app.default_callback_url or "",
        "status": app.status,
        "created_at": app.created_at,
    }


def get_open_app(
    x_api_key: str = Header(default="", alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> OpenApp:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="缺少 X-API-Key")
    app = db.query(OpenApp).filter(OpenApp.api_key == x_api_key, OpenApp.status == "ACTIVE").first()
    if not app:
        raise HTTPException(status_code=401, detail="无效的 API Key")
    return app


def _task_to_open(task: WorkTask, timeline: list = None) -> dict:
    return {
        "task_id": task.task_id,
        "worker_id": task.worker_id,
        "status": task.status.value if hasattr(task.status, "value") else task.status,
        "progress_note": task.progress_note or "",
        "result": task.result or None,
        "biz_task_id": task.biz_task_id or "",
        "tokens_used": task.tokens_used or 0,
        "created_at": task.created_at,
        "started_at": task.started_at,
        "finished_at": task.finished_at,
        "timeline": timeline or [],
    }


@open_router.get("/workers")
def open_list_workers(
    dept_id: Optional[str] = None,
    task_type: Optional[str] = None,
    status: str = "ON_DUTY",
    db: Session = Depends(get_db),
    app: OpenApp = Depends(get_open_app),
):
    q = db.query(DigitalWorker)
    if status:
        q = q.filter(DigitalWorker.status == status)
    if dept_id:
        q = q.filter(DigitalWorker.dept_id == dept_id)
    workers = q.all()
    items = []
    for w in workers:
        types = worker_task_types(db, w)
        if task_type and task_type not in types:
            continue
        role = db.query(DigitalRole).filter(DigitalRole.role_id == w.role_id).first()
        items.append({
            "worker_id": w.worker_id,
            "employee_no": w.employee_no,
            "name": w.name,
            "dept_id": w.dept_id,
            "role_name": role.name if role else "",
            "task_types": types,
            "status": w.status.value if hasattr(w.status, "value") else w.status,
        })
    return items


@open_router.get("/workers/{worker_id}/spec")
def open_worker_spec(
    worker_id: str,
    db: Session = Depends(get_db),
    app: OpenApp = Depends(get_open_app),
):
    worker = db.query(DigitalWorker).filter(DigitalWorker.worker_id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="数字员工不存在")
    return build_worker_spec(db, worker)


@open_router.post("/workers/{worker_id}/tasks", status_code=201)
def open_dispatch_task(
    worker_id: str,
    data: TaskCreate,
    db: Session = Depends(get_db),
    app: OpenApp = Depends(get_open_app),
):
    worker = db.query(DigitalWorker).filter(
        DigitalWorker.worker_id == worker_id,
        DigitalWorker.status == WorkerStatus.ON_DUTY,
    ).first()
    if not worker:
        raise HTTPException(status_code=404, detail="数字员工不可用")
    supported = worker_task_types(db, worker)
    if data.task_type and supported and data.task_type not in supported:
        raise HTTPException(status_code=422, detail="TASK_TYPE_NOT_SUPPORTED")
    if app.allowed_task_types and data.task_type and data.task_type not in app.allowed_task_types:
        raise HTTPException(status_code=403, detail="应用无权派发该 task_type")

    callback = data.callback_url or app.default_callback_url or ""
    task = create_and_start_task(
        db,
        worker=worker,
        source=TaskSource.OPEN_API,
        title=data.title,
        instruction=data.instruction,
        task_type=data.task_type,
        context=data.context,
        priority=data.priority,
        deadline=data.deadline,
        app_id=app.app_id,
        biz_task_id=data.biz_task_id or (data.context or {}).get("biz_task_id", ""),
        callback_url=callback,
        callback_events=data.callback_events,
        reporter=data.reporter or {"type": "APP", "app_id": app.app_id, "name": app.name},
    )
    schedule_task(task.task_id)
    return {
        "task_id": task.task_id,
        "worker_id": worker_id,
        "status": task.status.value if hasattr(task.status, "value") else task.status,
        "estimated": None,
        "created_at": task.created_at,
    }


@open_router.get("/tasks/{task_id}")
def open_get_task(
    task_id: str,
    db: Session = Depends(get_db),
    app: OpenApp = Depends(get_open_app),
):
    task = db.query(WorkTask).filter(WorkTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    from models import TaskEvent
    events = db.query(TaskEvent).filter(TaskEvent.task_id == task_id).order_by(TaskEvent.created_at).all()
    timeline = [{"status": e.event, "at": e.created_at} for e in events]
    return _task_to_open(task, timeline)


@open_router.get("/tasks")
def open_list_tasks(
    worker_id: Optional[str] = None,
    status: Optional[str] = None,
    biz_task_id: Optional[str] = None,
    db: Session = Depends(get_db),
    app: OpenApp = Depends(get_open_app),
):
    q = db.query(WorkTask).filter(WorkTask.app_id == app.app_id)
    if worker_id:
        q = q.filter(WorkTask.worker_id == worker_id)
    if status:
        q = q.filter(WorkTask.status == status)
    if biz_task_id:
        q = q.filter(WorkTask.biz_task_id == biz_task_id)
    items = q.order_by(WorkTask.created_at.desc()).limit(100).all()
    return [_task_to_open(t) for t in items]


@open_router.post("/tasks/{task_id}/cancel")
def open_cancel_task(
    task_id: str,
    db: Session = Depends(get_db),
    app: OpenApp = Depends(get_open_app),
):
    task = db.query(WorkTask).filter(WorkTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.app_id and task.app_id != app.app_id:
        raise HTTPException(status_code=403, detail="无权取消该任务")
    task = cancel_task(db, task_id, actor=f"app:{app.app_id}")
    return _task_to_open(task)


@open_router.post("/tasks/{task_id}/messages")
async def open_task_message(
    task_id: str,
    body: dict,
    db: Session = Depends(get_db),
    app: OpenApp = Depends(get_open_app),
):
    from services.hitl_bridge import handle_info_reply
    message = body.get("message") or body.get("content") or ""
    if not message:
        raise HTTPException(status_code=400, detail="缺少 message")
    return await handle_info_reply(db, task_id=task_id, message=message, user_id=f"app:{app.app_id}")
