from typing import Optional
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from database import get_db
from deps import get_current_user
from auth_config import PROJECT_DOCS_DIR
from models import (
    Project, ProjectItem, ProjectItemStatus, ProjectStatus,
    DigitalWorker, WorkTask, WorkerStatus, HumanUser, Message, TaskSource, TaskStatus,
    ProjectOwnerType, now_utc,
)
from schemas import (
    ProjectCreate, ProjectUpdate, ProjectItemCreate, ProjectItemUpdate, DelegateItemRequest,
)
from services.project_service import (
    project_to_dict, build_item_tree, item_to_dict, recalc_project_progress,
    find_or_create_direct_conv, list_workbench_workers, list_recent_activities,
    list_project_members, list_project_documents, create_project_document,
    list_project_activities, append_project_activity,
    update_project_status, delete_project,
)
from services.task_runner import create_and_start_task, schedule_task

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


def _ensure_owner(project: Project, user: HumanUser):
    if project.owner_id != user.user_id and user.role.value != "PLATFORM_ADMIN":
        raise HTTPException(status_code=403, detail="无权访问此项目")


def _get_owned_project(db: Session, project_id: str, user: HumanUser) -> Project:
    project = db.query(Project).filter(Project.project_id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    _ensure_owner(project, user)
    return project


@router.get("/workbench")
def get_workbench(db: Session = Depends(get_db), user: HumanUser = Depends(get_current_user)):
    projects = db.query(Project).filter(
        Project.owner_id == user.user_id,
        Project.status == ProjectStatus.ACTIVE,
    ).order_by(Project.sort, Project.created_at).all()

    pending = db.query(Message).filter(
        Message.msg_type == "approval_card",
    ).order_by(Message.created_at.desc()).limit(50).all()
    approvals = []
    for msg in pending:
        content = msg.content or {}
        if content.get("status") != "PENDING":
            continue
        item = db.query(ProjectItem).filter(ProjectItem.task_id == msg.ref_task_id).first() if msg.ref_task_id else None
        project = db.query(Project).filter(Project.project_id == item.project_id).first() if item else None
        if project and project.owner_id != user.user_id and user.role.value != "PLATFORM_ADMIN":
            continue
        worker = db.query(DigitalWorker).filter(DigitalWorker.worker_id == msg.sender_id).first()
        approvals.append({
            "msg_id": msg.msg_id,
            "task_id": msg.ref_task_id or "",
            "item_id": item.item_id if item else None,
            "item_name": item.name if item else "",
            "project_name": project.name if project else "",
            "worker_name": worker.name if worker else "",
            "title": content.get("text") or "操作授权审核",
            "status": content.get("status") or "PENDING",
            "content": content,
            "created_at": msg.created_at,
        })

    all_items = db.query(ProjectItem).join(Project).filter(Project.owner_id == user.user_id).all()
    done = sum(1 for i in all_items if i.status == ProjectItemStatus.COMPLETED)
    total = len(all_items)

    project_list = []
    for p in projects:
        d = project_to_dict(db, p)
        d["items"] = build_item_tree(db, p.project_id)
        project_list.append(d)

    return {
        "projects": project_list,
        "workers": list_workbench_workers(db),
        "pending_approvals": approvals,
        "workload_done": done,
        "workload_total": total,
        "recent_activities": list_recent_activities(db, user.user_id),
    }


@router.get("")
def list_projects(db: Session = Depends(get_db), user: HumanUser = Depends(get_current_user)):
    projects = db.query(Project).filter(
        Project.owner_id == user.user_id,
        Project.status == ProjectStatus.ACTIVE,
    ).order_by(Project.sort, Project.created_at).all()
    return {"items": [project_to_dict(db, p) for p in projects]}


@router.post("", status_code=201)
def create_project(
    data: ProjectCreate,
    db: Session = Depends(get_db),
    user: HumanUser = Depends(get_current_user),
):
    project = Project(
        owner_id=user.user_id,
        name=data.name,
        description=data.description,
        sort=data.sort,
    )
    db.add(project)
    db.flush()
    append_project_activity(
        db,
        project.project_id,
        "项目创建",
        kind="project",
        actor_type=ProjectOwnerType.HUMAN,
        actor_id=user.user_id,
        actor_name=user.name or "",
        commit=False,
    )
    db.commit()
    db.refresh(project)
    return project_to_dict(db, project)


@router.get("/items/{item_id}")
def get_item(item_id: str, db: Session = Depends(get_db), user: HumanUser = Depends(get_current_user)):
    item = db.query(ProjectItem).filter(ProjectItem.item_id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="事项不存在")
    project = db.query(Project).filter(Project.project_id == item.project_id).first()
    _ensure_owner(project, user)
    result = item_to_dict(db, item)
    if item.task_id:
        task = db.query(WorkTask).filter(WorkTask.task_id == item.task_id).first()
        if task:
            from routes.tasks import _task_dict
            result["task"] = _task_dict(db, task, with_timeline=True)
    return result


@router.get("/{project_id}")
def get_project(project_id: str, db: Session = Depends(get_db), user: HumanUser = Depends(get_current_user)):
    project = _get_owned_project(db, project_id, user)
    d = project_to_dict(db, project)
    d["items"] = build_item_tree(db, project_id)
    return d


@router.patch("/{project_id}")
def patch_project(
    project_id: str,
    data: ProjectUpdate,
    db: Session = Depends(get_db),
    user: HumanUser = Depends(get_current_user),
):
    project = _get_owned_project(db, project_id, user)
    payload = data.model_dump(exclude_unset=True)
    if "status" in payload and payload["status"] is not None:
        try:
            new_status = ProjectStatus(payload.pop("status"))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效状态: {data.status}")
        return project_to_dict(
            db,
            update_project_status(
                db,
                project,
                status=new_status,
                actor_id=user.user_id,
                actor_name=user.name or "",
            ),
        )
    for k, v in payload.items():
        setattr(project, k, v)
    project.updated_at = now_utc()
    db.commit()
    db.refresh(project)
    return project_to_dict(db, project)


@router.delete("/{project_id}", status_code=204)
def remove_project(
    project_id: str,
    db: Session = Depends(get_db),
    user: HumanUser = Depends(get_current_user),
):
    project = _get_owned_project(db, project_id, user)
    delete_project(db, project)
    return None


@router.get("/{project_id}/items")
def list_items(project_id: str, db: Session = Depends(get_db), user: HumanUser = Depends(get_current_user)):
    _get_owned_project(db, project_id, user)
    return {"items": build_item_tree(db, project_id)}


@router.get("/{project_id}/members")
def get_members(project_id: str, db: Session = Depends(get_db), user: HumanUser = Depends(get_current_user)):
    project = _get_owned_project(db, project_id, user)
    return {"items": list_project_members(db, project)}


@router.get("/{project_id}/documents")
def get_documents(project_id: str, db: Session = Depends(get_db), user: HumanUser = Depends(get_current_user)):
    _get_owned_project(db, project_id, user)
    return {"items": list_project_documents(db, project_id)}


@router.post("/{project_id}/documents", status_code=201)
async def upload_document(
    project_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: HumanUser = Depends(get_current_user),
):
    project = _get_owned_project(db, project_id, user)
    PROJECT_DOCS_DIR.mkdir(parents=True, exist_ok=True)
    original = file.filename or "upload.bin"
    suffix = Path(original).suffix
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    dest = PROJECT_DOCS_DIR / stored_name
    content = await file.read()
    dest.write_bytes(content)
    return create_project_document(
        db,
        project,
        name=original,
        file_path=f"/project-docs/{stored_name}",
        mime_type=file.content_type or "",
        size_bytes=len(content),
        owner_id=user.user_id,
        owner_name=user.name or "",
    )


@router.get("/{project_id}/activities")
def get_activities(project_id: str, db: Session = Depends(get_db), user: HumanUser = Depends(get_current_user)):
    _get_owned_project(db, project_id, user)
    return {"items": list_project_activities(db, project_id)}


@router.post("/{project_id}/items", status_code=201)
def create_item(
    project_id: str,
    data: ProjectItemCreate,
    db: Session = Depends(get_db),
    user: HumanUser = Depends(get_current_user),
):
    _get_owned_project(db, project_id, user)
    if data.parent_id:
        parent = db.query(ProjectItem).filter(
            ProjectItem.item_id == data.parent_id,
            ProjectItem.project_id == project_id,
        ).first()
        if not parent:
            raise HTTPException(status_code=404, detail="父事项不存在")
    item = ProjectItem(
        project_id=project_id,
        parent_id=data.parent_id,
        name=data.name,
        description=data.description,
        sort=data.sort,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    recalc_project_progress(db, project_id)
    return item_to_dict(db, item)


@router.patch("/items/{item_id}")
def update_item(
    item_id: str,
    data: ProjectItemUpdate,
    db: Session = Depends(get_db),
    user: HumanUser = Depends(get_current_user),
):
    item = db.query(ProjectItem).filter(ProjectItem.item_id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="事项不存在")
    project = db.query(Project).filter(Project.project_id == item.project_id).first()
    _ensure_owner(project, user)
    if data.name is not None:
        item.name = data.name
    if data.description is not None:
        item.description = data.description
    if data.status is not None:
        try:
            new_status = ProjectItemStatus(data.status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效状态: {data.status}")
        # Pausing: always mark running steps as suspended; cancel active task if needed
        if new_status == ProjectItemStatus.SUSPENDED:
            from services.item_lifecycle import apply_pause_to_item_and_task
            apply_pause_to_item_and_task(db, item, actor=user.user_id)
        item.status = new_status
    if data.worker_id is not None:
        item.worker_id = data.worker_id or None
    if data.progress_pct is not None:
        item.progress_pct = data.progress_pct
    if data.meta is not None:
        item.meta = data.meta
    db.commit()
    db.refresh(item)
    recalc_project_progress(db, item.project_id)
    return item_to_dict(db, item)


@router.delete("/items/{item_id}", status_code=204)
def delete_item(
    item_id: str,
    db: Session = Depends(get_db),
    user: HumanUser = Depends(get_current_user),
):
    item = db.query(ProjectItem).filter(ProjectItem.item_id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="事项不存在")
    project = db.query(Project).filter(Project.project_id == item.project_id).first()
    _ensure_owner(project, user)

    child_count = db.query(ProjectItem).filter(ProjectItem.parent_id == item_id).count()
    if child_count:
        raise HTTPException(status_code=400, detail=f"仍有 {child_count} 个子事项，请先删除子事项")

    if item.task_id:
        task = db.query(WorkTask).filter(WorkTask.task_id == item.task_id).first()
        if task and task.status not in (
            TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELED,
        ):
            from services.task_runner import cancel_task
            try:
                cancel_task(db, item.task_id, actor=user.user_id)
            except Exception:
                pass
        # detach task FK before deleting item
        item.task_id = None
        db.flush()
        if task:
            task.item_id = None

    project_id = item.project_id
    append_project_activity(
        db,
        project_id,
        f"删除事项「{item.name}」",
        kind="update",
        actor_type=ProjectOwnerType.HUMAN,
        actor_id=user.user_id,
        actor_name=user.name or "",
        commit=False,
    )
    db.delete(item)
    db.commit()
    recalc_project_progress(db, project_id)
    return None


@router.post("/items/{item_id}/delegate")
def delegate_item(
    item_id: str,
    data: DelegateItemRequest,
    db: Session = Depends(get_db),
    user: HumanUser = Depends(get_current_user),
):
    item = db.query(ProjectItem).filter(ProjectItem.item_id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="事项不存在")
    project = db.query(Project).filter(Project.project_id == item.project_id).first()
    _ensure_owner(project, user)

    worker = db.query(DigitalWorker).filter(
        DigitalWorker.worker_id == data.worker_id,
        DigitalWorker.status == WorkerStatus.ON_DUTY,
    ).first()
    if not worker:
        raise HTTPException(status_code=404, detail="数字员工不可用")

    conv_id = data.conv_id or find_or_create_direct_conv(db, user.user_id, worker.worker_id)

    meta = dict(item.meta or {})
    meta["delegate_instruction"] = data.instruction
    meta["delegate_task_type"] = data.task_type or ""
    meta["delegate_conv_id"] = conv_id

    item.worker_id = worker.worker_id
    item.status = ProjectItemStatus.DELEGATED
    item.meta = meta

    task = None
    if data.auto_start:
        task = create_and_start_task(
            db,
            worker=worker,
            source=TaskSource.BPM,
            title=item.name,
            instruction=data.instruction,
            task_type=data.task_type,
            context={
                "project_id": item.project_id,
                "item_id": item.item_id,
                "project_name": project.name if project else "",
                "item_description": item.description or "",
                "planned_start": item.planned_start.isoformat() if item.planned_start else None,
                "planned_end": item.planned_end.isoformat() if item.planned_end else None,
            },
            conv_id=conv_id,
            reporter={"type": "HUMAN", "user_id": user.user_id, "name": user.name},
            project_id=item.project_id,
            item_id=item.item_id,
        )
        item.task_id = task.task_id
    else:
        item.task_id = None

    append_project_activity(
        db,
        item.project_id,
        f"委派「{item.name}」给{worker.name}" + ("并启动" if data.auto_start else "（待确认启动）"),
        kind="delegate",
        actor_type=ProjectOwnerType.HUMAN,
        actor_id=user.user_id,
        actor_name=user.name or "",
        commit=False,
    )
    db.commit()
    if task is not None:
        schedule_task(task.task_id)

    from routes.tasks import _task_dict
    return {
        "item": item_to_dict(db, item),
        "task": _task_dict(db, task) if task else None,
        "conv_id": conv_id,
    }


@router.post("/items/{item_id}/start")
def start_item(
    item_id: str,
    db: Session = Depends(get_db),
    user: HumanUser = Depends(get_current_user),
):
    """人工确认后启动已委派事项：创建 WorkTask 并 schedule。"""
    item = db.query(ProjectItem).filter(ProjectItem.item_id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="事项不存在")
    project = db.query(Project).filter(Project.project_id == item.project_id).first()
    _ensure_owner(project, user)

    from routes.tasks import _task_dict

    # Idempotent: already linked to a task (status may have advanced after schedule)
    if item.task_id:
        task = db.query(WorkTask).filter(WorkTask.task_id == item.task_id).first()
        if task:
            if task.status in (TaskStatus.RECEIVED, TaskStatus.QUEUED):
                schedule_task(task.task_id)
            return {
                "item": item_to_dict(db, item),
                "task": _task_dict(db, task),
            }
        item.task_id = None

    if item.status != ProjectItemStatus.DELEGATED:
        raise HTTPException(status_code=400, detail="仅已委派且待启动的事项可确认启动")
    if not item.worker_id:
        raise HTTPException(status_code=400, detail="事项未绑定数字员工")

    worker = db.query(DigitalWorker).filter(
        DigitalWorker.worker_id == item.worker_id,
        DigitalWorker.status == WorkerStatus.ON_DUTY,
    ).first()
    if not worker:
        raise HTTPException(status_code=404, detail="数字员工不可用")

    meta = dict(item.meta or {})
    instruction = (meta.get("delegate_instruction") or item.description or item.name or "").strip()
    if not instruction:
        instruction = f"请处理事项：{item.name}"
    task_type = meta.get("delegate_task_type") or ""
    conv_id = meta.get("delegate_conv_id") or find_or_create_direct_conv(
        db, user.user_id, worker.worker_id,
    )

    task = create_and_start_task(
        db,
        worker=worker,
        source=TaskSource.BPM,
        title=item.name,
        instruction=instruction,
        task_type=task_type,
        context={
            "project_id": item.project_id,
            "item_id": item.item_id,
            "project_name": project.name if project else "",
            "item_description": item.description or "",
            "planned_start": item.planned_start.isoformat() if item.planned_start else None,
            "planned_end": item.planned_end.isoformat() if item.planned_end else None,
        },
        conv_id=conv_id,
        reporter={"type": "HUMAN", "user_id": user.user_id, "name": user.name},
        project_id=item.project_id,
        item_id=item.item_id,
    )
    item.task_id = task.task_id
    append_project_activity(
        db,
        item.project_id,
        f"确认启动「{item.name}」（{worker.name}）",
        kind="start",
        actor_type=ProjectOwnerType.HUMAN,
        actor_id=user.user_id,
        actor_name=user.name or "",
        commit=False,
    )
    db.commit()
    schedule_task(task.task_id)

    return {
        "item": item_to_dict(db, item),
        "task": _task_dict(db, task),
        "conv_id": conv_id,
    }


@router.post("/items/{item_id}/resume")
def resume_item(
    item_id: str,
    db: Session = Depends(get_db),
    user: HumanUser = Depends(get_current_user),
):
    """Continue a paused item: restore pending steps and schedule execution."""
    item = db.query(ProjectItem).filter(ProjectItem.item_id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="事项不存在")
    project = db.query(Project).filter(Project.project_id == item.project_id).first()
    _ensure_owner(project, user)

    if item.status != ProjectItemStatus.SUSPENDED:
        raise HTTPException(status_code=400, detail="仅已暂停的事项可继续执行")
    if not item.worker_id:
        raise HTTPException(status_code=400, detail="事项未绑定数字员工")

    worker = db.query(DigitalWorker).filter(
        DigitalWorker.worker_id == item.worker_id,
        DigitalWorker.status == WorkerStatus.ON_DUTY,
    ).first()
    if not worker:
        raise HTTPException(status_code=404, detail="数字员工不可用")

    from services.item_lifecycle import normalize_steps_on_resume
    from routes.tasks import _task_dict

    meta = dict(item.meta or {})
    old_task = None
    if item.task_id:
        old_task = db.query(WorkTask).filter(WorkTask.task_id == item.task_id).first()

    prior_steps = []
    if old_task and old_task.progress_steps:
        prior_steps = list(old_task.progress_steps)
    elif meta.get("progress_steps"):
        prior_steps = list(meta.get("progress_steps") or [])
    resumed_steps = normalize_steps_on_resume(prior_steps)

    instruction = (meta.get("delegate_instruction") or item.description or item.name or "").strip()
    if not instruction:
        instruction = f"请继续处理事项：{item.name}"
    task_type = meta.get("delegate_task_type") or (old_task.task_type if old_task else "") or ""
    conv_id = meta.get("delegate_conv_id") or find_or_create_direct_conv(
        db, user.user_id, worker.worker_id,
    )

    # Always create a fresh runnable task; carry resumed steps so orchestrator can skip completed
    task = create_and_start_task(
        db,
        worker=worker,
        source=TaskSource.BPM,
        title=item.name,
        instruction=instruction,
        task_type=task_type,
        context={
            "project_id": item.project_id,
            "item_id": item.item_id,
            "project_name": project.name if project else "",
            "item_description": item.description or "",
            "planned_start": item.planned_start.isoformat() if item.planned_start else None,
            "planned_end": item.planned_end.isoformat() if item.planned_end else None,
            "resume": True,
        },
        conv_id=conv_id,
        reporter={"type": "HUMAN", "user_id": user.user_id, "name": user.name},
        project_id=item.project_id,
        item_id=item.item_id,
    )
    if resumed_steps:
        task.progress_steps = resumed_steps
        task.progress_pct = item.progress_pct or task.progress_pct or 5
        if old_task and old_task.result:
            task.result = dict(old_task.result)
        db.commit()
        db.refresh(task)

    item.task_id = task.task_id
    item.status = ProjectItemStatus.DELEGATED
    meta["progress_steps"] = resumed_steps
    meta["progress_note"] = "已继续执行"
    meta["delegate_conv_id"] = conv_id
    item.meta = meta
    append_project_activity(
        db,
        item.project_id,
        f"继续执行「{item.name}」（{worker.name}）",
        kind="resume",
        actor_type=ProjectOwnerType.HUMAN,
        actor_id=user.user_id,
        actor_name=user.name or "",
        commit=False,
    )
    db.commit()
    schedule_task(task.task_id)

    return {
        "item": item_to_dict(db, item),
        "task": _task_dict(db, task),
        "conv_id": conv_id,
    }
