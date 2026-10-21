from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import Optional
from database import get_db, SessionLocal
from models import WorkTask, TaskEvent, DigitalWorker, HumanUser, TaskSource, WorkerStatus
from schemas import TaskCreate, TaskResponse, PaginatedResponse
from deps import get_current_user, require_admin
from services.task_runner import create_and_start_task, cancel_task, schedule_task
from services.ws_hub import ws_manager

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


def _task_dict(db: Session, task: WorkTask, with_timeline: bool = False) -> dict:
    d = {
        "task_id": task.task_id,
        "worker_id": task.worker_id,
        "duty_id": task.duty_id,
        "source": task.source.value if hasattr(task.source, "value") else task.source,
        "task_type": task.task_type or "",
        "title": task.title,
        "instruction": task.instruction,
        "context": task.context or {},
        "priority": task.priority,
        "deadline": task.deadline,
        "status": task.status.value if hasattr(task.status, "value") else task.status,
        "status_detail": task.status_detail or "",
        "conv_id": task.conv_id,
        "app_id": task.app_id,
        "biz_task_id": task.biz_task_id or "",
        "agent_session_id": task.agent_session_id or "",
        "project_id": task.project_id,
        "item_id": task.item_id,
        "progress_note": task.progress_note or "",
        "progress_pct": task.progress_pct or 0,
        "progress_steps": task.progress_steps or [],
        "result": task.result or {},
        "artifacts": task.artifacts or [],
        "tokens_used": task.tokens_used or 0,
        "reporter": task.reporter or {},
        "created_at": task.created_at,
        "started_at": task.started_at,
        "finished_at": task.finished_at,
        "timeline": [],
    }
    if with_timeline:
        events = db.query(TaskEvent).filter(TaskEvent.task_id == task.task_id).order_by(TaskEvent.created_at).all()
        d["timeline"] = [
            {"event": e.event, "detail": e.detail, "actor": e.actor, "at": e.created_at}
            for e in events
        ]
    return d


@router.get("")
def list_tasks(
    worker_id: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: HumanUser = Depends(get_current_user),
):
    q = db.query(WorkTask)
    if worker_id:
        q = q.filter(WorkTask.worker_id == worker_id)
    if status:
        q = q.filter(WorkTask.status == status)
    total = q.count()
    items = q.order_by(WorkTask.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return PaginatedResponse(
        total=total, page=page, page_size=page_size,
        items=[_task_dict(db, t) for t in items],
    )


@router.post("", status_code=201)
def create_task(
    data: TaskCreate,
    worker_id: str = Query(...),
    db: Session = Depends(get_db),
    user: HumanUser = Depends(get_current_user),
):
    worker = db.query(DigitalWorker).filter(
        DigitalWorker.worker_id == worker_id,
        DigitalWorker.status == WorkerStatus.ON_DUTY,
    ).first()
    if not worker:
        raise HTTPException(status_code=404, detail="数字员工不可用")
    task = create_and_start_task(
        db,
        worker=worker,
        source=TaskSource.IM,
        title=data.title,
        instruction=data.instruction,
        task_type=data.task_type,
        context=data.context,
        priority=data.priority,
        deadline=data.deadline,
        conv_id=data.conv_id,
        callback_url=data.callback_url,
        callback_events=data.callback_events,
        reporter=data.reporter or {"type": "HUMAN", "user_id": user.user_id, "name": user.name},
        biz_task_id=data.biz_task_id,
    )
    schedule_task(task.task_id)
    return _task_dict(db, task)


@router.get("/{task_id}")
def get_task(task_id: str, db: Session = Depends(get_db), user: HumanUser = Depends(get_current_user)):
    task = db.query(WorkTask).filter(WorkTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _task_dict(db, task, with_timeline=True)


@router.post("/{task_id}/cancel")
def cancel(task_id: str, db: Session = Depends(get_db), user: HumanUser = Depends(get_current_user)):
    task = cancel_task(db, task_id, actor=user.user_id)
    return _task_dict(db, task)


@router.websocket("/ws/{user_id}")
async def unused():
    pass


# Separate WS router
ws_router = APIRouter(tags=["ws"])


@ws_router.websocket("/api/v1/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    from security import decode_token

    db = SessionLocal()
    try:
        try:
            payload = decode_token(token)
            username = payload.get("sub")
        except ValueError:
            await websocket.close(code=4401)
            return
        if not username:
            await websocket.close(code=4401)
            return
        user = db.query(HumanUser).filter(HumanUser.username == username).first()
        if not user or user.status != "ACTIVE":
            await websocket.close(code=4401)
            return
        user_id = user.user_id
    finally:
        db.close()

    await ws_manager.connect(user_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        await ws_manager.disconnect(user_id, websocket)
    except Exception:
        await ws_manager.disconnect(user_id, websocket)
