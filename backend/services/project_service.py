"""Project / item helpers for the demo workbench."""
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from models import (
    Project, ProjectItem, ProjectItemStatus, ProjectStatus,
    ProjectDocument, ProjectActivity, ProjectDocSource, ProjectOwnerType,
    DigitalWorker, WorkTask, TaskStatus, WorkerStatus, Duty, WorkerDutyAgent,
    HumanUser, Department, Conversation, ConversationMember, MemberType, ConvType,
    Message, gen_uuid,
)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _worker_name(db: Session, worker_id: Optional[str]) -> str:
    if not worker_id:
        return ""
    w = db.query(DigitalWorker).filter(DigitalWorker.worker_id == worker_id).first()
    return w.name if w else ""


def _owner_info(db: Session, owner_id: Optional[str]) -> dict:
    if not owner_id:
        return {"user_id": "", "name": "", "avatar": "", "title": "", "dept_name": ""}
    user = db.query(HumanUser).filter(HumanUser.user_id == owner_id).first()
    if not user:
        return {"user_id": owner_id, "name": "", "avatar": "", "title": "", "dept_name": ""}
    dept_name = ""
    if user.dept_id:
        dept = db.query(Department).filter(Department.dept_id == user.dept_id).first()
        dept_name = dept.name if dept else ""
    return {
        "user_id": user.user_id,
        "name": user.name or "",
        "avatar": user.avatar or "",
        "title": user.title or "",
        "dept_name": dept_name,
    }


def item_to_dict(db: Session, item: ProjectItem, children: Optional[List[dict]] = None) -> dict:
    return {
        "item_id": item.item_id,
        "project_id": item.project_id,
        "parent_id": item.parent_id,
        "name": item.name,
        "description": item.description or "",
        "status": item.status.value if hasattr(item.status, "value") else item.status,
        "sort": item.sort or 0,
        "worker_id": item.worker_id,
        "worker_name": _worker_name(db, item.worker_id),
        "task_id": item.task_id,
        "progress_pct": item.progress_pct or 0,
        "meta": item.meta or {},
        "planned_start": item.planned_start,
        "planned_end": item.planned_end,
        "completed_at": item.completed_at,
        "children": children or [],
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def project_stats(db: Session, project_id: str) -> Tuple[int, int, int, int]:
    items = db.query(ProjectItem).filter(ProjectItem.project_id == project_id).all()
    total = len(items)
    completed = sum(1 for i in items if i.status == ProjectItemStatus.COMPLETED)
    in_progress = sum(1 for i in items if i.status in (ProjectItemStatus.IN_PROGRESS, ProjectItemStatus.DELEGATED))
    delegated = sum(1 for i in items if i.status == ProjectItemStatus.DELEGATED)
    return total, completed, in_progress, delegated


def project_to_dict(db: Session, project: Project) -> dict:
    total, completed, in_progress, delegated = project_stats(db, project.project_id)
    return {
        "project_id": project.project_id,
        "owner_id": project.owner_id,
        "name": project.name,
        "description": project.description or "",
        "status": project.status.value if hasattr(project.status, "value") else project.status,
        "progress_pct": project.progress_pct or 0,
        "sort": project.sort or 0,
        "item_count": total,
        "completed_count": completed,
        "in_progress_count": in_progress,
        "delegated_count": delegated,
        "start_date": project.start_date,
        "end_date": project.end_date,
        "owner": _owner_info(db, project.owner_id),
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }


def update_project_status(
    db: Session,
    project: Project,
    *,
    status: ProjectStatus,
    actor_id: str = "",
    actor_name: str = "",
) -> Project:
    project.status = status
    if status == ProjectStatus.COMPLETED:
        project.progress_pct = max(project.progress_pct or 0, 100)
    project.updated_at = _now_utc()
    labels = {
        ProjectStatus.SUSPENDED: "项目已中止",
        ProjectStatus.COMPLETED: "项目已完成",
        ProjectStatus.ARCHIVED: "项目已归档",
        ProjectStatus.ACTIVE: "项目已恢复",
    }
    append_project_activity(
        db,
        project.project_id,
        labels.get(status, f"项目状态更新为 {status.value}"),
        kind="status",
        actor_type=ProjectOwnerType.HUMAN,
        actor_id=actor_id,
        actor_name=actor_name,
        commit=False,
    )
    db.commit()
    db.refresh(project)
    return project


def delete_project(db: Session, project: Project) -> None:
    """Hard-delete a project and related rows (respect FK order)."""
    project_id = project.project_id
    items = db.query(ProjectItem).filter(ProjectItem.project_id == project_id).all()
    for item in items:
        item.task_id = None
    db.flush()
    # Clear self-FK parent links then delete items
    for item in items:
        item.parent_id = None
    db.flush()
    db.query(ProjectItem).filter(ProjectItem.project_id == project_id).delete(synchronize_session=False)
    db.query(ProjectDocument).filter(ProjectDocument.project_id == project_id).delete(synchronize_session=False)
    db.query(ProjectActivity).filter(ProjectActivity.project_id == project_id).delete(synchronize_session=False)
    # Detach work tasks (nullable FK) rather than deleting execution history
    tasks = db.query(WorkTask).filter(WorkTask.project_id == project_id).all()
    for task in tasks:
        task.project_id = None
        task.item_id = None
    db.delete(project)
    db.commit()


def build_item_tree(db: Session, project_id: str) -> List[dict]:
    items = db.query(ProjectItem).filter(
        ProjectItem.project_id == project_id,
    ).order_by(ProjectItem.sort, ProjectItem.created_at).all()
    by_parent: Dict[Optional[str], List[ProjectItem]] = {}
    for item in items:
        by_parent.setdefault(item.parent_id, []).append(item)

    def build(parent_id: Optional[str]) -> List[dict]:
        nodes = []
        for item in by_parent.get(parent_id, []):
            nodes.append(item_to_dict(db, item, build(item.item_id)))
        return nodes

    return build(None)


def recalc_project_progress(db: Session, project_id: str):
    project = db.query(Project).filter(Project.project_id == project_id).first()
    if not project:
        return
    items = db.query(ProjectItem).filter(ProjectItem.project_id == project_id).all()
    if not items:
        project.progress_pct = 0
    else:
        project.progress_pct = int(sum(i.progress_pct or 0 for i in items) / len(items))
    db.commit()


def append_project_activity(
    db: Session,
    project_id: str,
    text: str,
    *,
    kind: str = "update",
    actor_type: ProjectOwnerType = ProjectOwnerType.HUMAN,
    actor_id: str = "",
    actor_name: str = "",
    commit: bool = True,
) -> ProjectActivity:
    activity = ProjectActivity(
        activity_id=gen_uuid(),
        project_id=project_id,
        kind=kind,
        text=text,
        actor_type=actor_type,
        actor_id=actor_id or "",
        actor_name=actor_name or "",
    )
    db.add(activity)
    if commit:
        db.commit()
        db.refresh(activity)
    return activity


def sync_item_from_task(db: Session, task: WorkTask):
    if not task.item_id:
        return
    item = db.query(ProjectItem).filter(ProjectItem.item_id == task.item_id).first()
    if not item:
        return

    prev_pct = item.progress_pct or 0
    item.progress_pct = task.progress_pct or item.progress_pct or 0
    meta = dict(item.meta or {})
    if task.progress_steps:
        meta["progress_steps"] = task.progress_steps
    if task.progress_note:
        meta["progress_note"] = task.progress_note
    if task.result:
        if task.result.get("intent"):
            meta["intent"] = task.result["intent"]
        if task.result.get("report") or task.result.get("summary"):
            meta["report"] = task.result.get("report") or task.result.get("summary")
    if task.artifacts:
        meta["artifacts"] = task.artifacts
    item.meta = meta

    status = task.status.value if hasattr(task.status, "value") else task.status
    worker = db.query(DigitalWorker).filter(DigitalWorker.worker_id == task.worker_id).first()
    actor_name = worker.name if worker else "数字员工"

    if status == TaskStatus.COMPLETED.value:
        item.status = ProjectItemStatus.COMPLETED
        item.progress_pct = max(item.progress_pct or 0, 100)
        if not item.completed_at:
            item.completed_at = task.finished_at or _now_utc()
        append_project_activity(
            db,
            item.project_id,
            f"「{item.name}」已完成",
            kind="completed",
            actor_type=ProjectOwnerType.WORKER,
            actor_id=task.worker_id or "",
            actor_name=actor_name,
            commit=False,
        )
    elif status == TaskStatus.FAILED.value:
        if item.status != ProjectItemStatus.COMPLETED:
            item.status = ProjectItemStatus.IN_PROGRESS
    elif status == TaskStatus.CANCELED.value:
        # Pausing sets item to SUSPENDED then cancels the task — keep SUSPENDED.
        # Only clear back to TODO when cancel is not from an explicit pause.
        if item.status != ProjectItemStatus.SUSPENDED:
            item.status = ProjectItemStatus.TODO
            item.task_id = None
        # Always refresh meta steps so UI does not keep stale "running" steps
        if task.progress_steps:
            meta = dict(item.meta or {})
            meta["progress_steps"] = task.progress_steps
            meta["progress_note"] = task.progress_note or meta.get("progress_note") or "已暂停"
            item.meta = meta
    elif status in (
        TaskStatus.RUNNING.value,
        TaskStatus.NEED_HUMAN.value,
        TaskStatus.RECEIVED.value,
        TaskStatus.QUEUED.value,
    ):
        if item.status != ProjectItemStatus.COMPLETED:
            item.status = (
                ProjectItemStatus.IN_PROGRESS
                if status == TaskStatus.RUNNING.value
                else ProjectItemStatus.DELEGATED
            )
        if status == TaskStatus.RUNNING.value and (item.progress_pct or 0) != prev_pct:
            pct = item.progress_pct or 0
            append_project_activity(
                db,
                item.project_id,
                f"{item.name}进度更新至 {pct}%",
                kind="progress",
                actor_type=ProjectOwnerType.WORKER,
                actor_id=task.worker_id or "",
                actor_name=actor_name,
                commit=False,
            )

    db.commit()
    recalc_project_progress(db, item.project_id)


def document_to_dict(doc: ProjectDocument) -> dict:
    return {
        "doc_id": doc.doc_id,
        "project_id": doc.project_id,
        "name": doc.name,
        "file_path": doc.file_path or "",
        "mime_type": doc.mime_type or "",
        "size_bytes": doc.size_bytes or 0,
        "source": doc.source.value if hasattr(doc.source, "value") else doc.source,
        "owner_type": doc.owner_type.value if hasattr(doc.owner_type, "value") else doc.owner_type,
        "owner_id": doc.owner_id or "",
        "owner_name": doc.owner_name or "",
        "created_at": doc.created_at,
        "updated_at": doc.updated_at,
    }


def activity_to_dict(activity: ProjectActivity) -> dict:
    return {
        "activity_id": activity.activity_id,
        "project_id": activity.project_id,
        "kind": activity.kind or "update",
        "text": activity.text or "",
        "actor_type": activity.actor_type.value if hasattr(activity.actor_type, "value") else activity.actor_type,
        "actor_id": activity.actor_id or "",
        "actor_name": activity.actor_name or "",
        "created_at": activity.created_at,
    }


def list_project_members(db: Session, project: Project) -> List[dict]:
    owner = _owner_info(db, project.owner_id)
    members = [{
        "key": f"owner-{owner['user_id']}",
        "name": owner["name"] or "项目负责人",
        "role": owner["title"] or "项目负责人",
        "subtitle": owner["dept_name"] or "负责人",
        "is_worker": False,
        "avatar": owner["avatar"],
        "activity": "",
        "tag": "项目负责人",
    }]
    items = db.query(ProjectItem).filter(
        ProjectItem.project_id == project.project_id,
        ProjectItem.worker_id.isnot(None),
    ).all()
    seen = set()
    for item in items:
        wid = item.worker_id
        if not wid or wid in seen:
            continue
        seen.add(wid)
        worker = db.query(DigitalWorker).filter(DigitalWorker.worker_id == wid).first()
        act = worker_activity(db, worker) if worker else {"activity": "online"}
        activity = act.get("activity") or "online"
        tag = "执行中" if activity == "working" else "已参与"
        members.append({
            "key": wid,
            "name": (worker.name if worker else None) or _worker_name(db, wid) or "数字员工",
            "role": "数字员工",
            "subtitle": "数字员工",
            "is_worker": True,
            "avatar": (worker.avatar if worker else "") or "",
            "activity": activity,
            "tag": tag,
        })
    return members


def list_project_documents(db: Session, project_id: str) -> List[dict]:
    docs = (
        db.query(ProjectDocument)
        .filter(ProjectDocument.project_id == project_id)
        .order_by(ProjectDocument.updated_at.desc(), ProjectDocument.created_at.desc())
        .all()
    )
    return [document_to_dict(d) for d in docs]


def create_project_document(
    db: Session,
    project: Project,
    *,
    name: str,
    file_path: str,
    mime_type: str,
    size_bytes: int,
    owner_id: str,
    owner_name: str,
    source: ProjectDocSource = ProjectDocSource.UPLOAD,
    owner_type: ProjectOwnerType = ProjectOwnerType.HUMAN,
) -> dict:
    doc = ProjectDocument(
        doc_id=gen_uuid(),
        project_id=project.project_id,
        name=name,
        file_path=file_path,
        mime_type=mime_type or "",
        size_bytes=size_bytes or 0,
        source=source,
        owner_type=owner_type,
        owner_id=owner_id or "",
        owner_name=owner_name or "",
    )
    db.add(doc)
    append_project_activity(
        db,
        project.project_id,
        f"上传文档「{name}」",
        kind="document",
        actor_type=owner_type,
        actor_id=owner_id or "",
        actor_name=owner_name or "",
        commit=False,
    )
    db.commit()
    db.refresh(doc)
    return document_to_dict(doc)


def list_project_activities(db: Session, project_id: str, limit: int = 50) -> List[dict]:
    rows = (
        db.query(ProjectActivity)
        .filter(ProjectActivity.project_id == project_id)
        .order_by(ProjectActivity.created_at.desc())
        .limit(limit)
        .all()
    )
    return [activity_to_dict(a) for a in rows]


def find_or_create_direct_conv(db: Session, user_id: str, worker_id: str) -> str:
    """Find existing DIRECT conversation between human and worker, or create one."""
    worker_convs = db.query(ConversationMember.conv_id).filter(
        ConversationMember.member_type == MemberType.WORKER,
        ConversationMember.member_id == worker_id,
    ).all()
    conv_ids = [r[0] for r in worker_convs]
    if conv_ids:
        match = db.query(ConversationMember).filter(
            ConversationMember.conv_id.in_(conv_ids),
            ConversationMember.member_type == MemberType.HUMAN,
            ConversationMember.member_id == user_id,
        ).first()
        if match:
            conv = db.query(Conversation).filter(Conversation.conv_id == match.conv_id).first()
            if conv and conv.type == ConvType.DIRECT:
                return conv.conv_id

    worker = db.query(DigitalWorker).filter(DigitalWorker.worker_id == worker_id).first()
    user = db.query(HumanUser).filter(HumanUser.user_id == user_id).first()
    conv = Conversation(
        conv_id=gen_uuid(),
        type=ConvType.DIRECT,
        name=f"{user.name if user else '用户'} & {worker.name if worker else '数字员工'}",
        owner_id=user_id,
    )
    db.add(conv)
    db.flush()
    db.add(ConversationMember(conv_id=conv.conv_id, member_type=MemberType.HUMAN, member_id=user_id))
    db.add(ConversationMember(conv_id=conv.conv_id, member_type=MemberType.WORKER, member_id=worker_id))
    db.commit()
    return conv.conv_id


def worker_activity(db: Session, worker: DigitalWorker) -> dict:
    worker_status = worker.status.value if hasattr(worker.status, "value") else worker.status
    if worker_status != WorkerStatus.ON_DUTY.value:
        return {
            "activity": "offline",
            "current_task_title": "",
            "progress_pct": 0,
        }

    active = db.query(WorkTask).filter(
        WorkTask.worker_id == worker.worker_id,
        WorkTask.status.in_([
            TaskStatus.RUNNING, TaskStatus.NEED_HUMAN,
        ]),
    ).order_by(WorkTask.created_at.desc()).first()

    if active:
        return {
            "activity": "working",
            "current_task_title": active.title or "",
            "progress_pct": active.progress_pct or 0,
        }
    return {
        "activity": "online",
        "current_task_title": "",
        "progress_pct": 0,
    }


def _worker_description(db: Session, worker: DigitalWorker) -> str:
    if worker.remark:
        return worker.remark
    duty_ids = [
        r.duty_id for r in db.query(WorkerDutyAgent).filter(
            WorkerDutyAgent.worker_id == worker.worker_id,
        ).all()
    ]
    if not duty_ids:
        return ""
    duties = db.query(Duty).filter(Duty.duty_id.in_(duty_ids)).all()
    names = [d.name for d in duties if d.name]
    if not names:
        return ""
    return f"负责：{'、'.join(names[:4])}"


def list_workbench_workers(db: Session) -> List[dict]:
    workers = db.query(DigitalWorker).filter(
        DigitalWorker.status.in_([WorkerStatus.ON_DUTY, WorkerStatus.SUSPENDED]),
    ).order_by(DigitalWorker.name).all()
    now = _now_utc()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    result = []
    for w in workers:
        act = worker_activity(db, w)
        today_done = db.query(WorkTask).filter(
            WorkTask.worker_id == w.worker_id,
            WorkTask.status == TaskStatus.COMPLETED,
            WorkTask.finished_at >= today_start,
        ).count()
        week_done = db.query(WorkTask).filter(
            WorkTask.worker_id == w.worker_id,
            WorkTask.status == TaskStatus.COMPLETED,
            WorkTask.finished_at >= week_start,
        ).count()
        today_total = db.query(WorkTask).filter(
            WorkTask.worker_id == w.worker_id,
            WorkTask.created_at >= today_start,
        ).count()
        result.append({
            "worker_id": w.worker_id,
            "name": w.name,
            "employee_no": w.employee_no,
            "status": w.status.value if hasattr(w.status, "value") else w.status,
            "description": _worker_description(db, w),
            "today_task_count": today_total,
            "today_done_count": today_done,
            "week_done_count": week_done,
            **act,
        })
    return result


def list_recent_activities(db: Session, owner_id: str, limit: int = 8) -> List[dict]:
    """Build a lightweight activity feed for the workbench home."""
    activities: List[dict] = []
    projects = db.query(Project).filter(Project.owner_id == owner_id).all()
    owned_project_ids = {p.project_id for p in projects}

    if owned_project_ids:
        tasks = (
            db.query(WorkTask)
            .filter(WorkTask.project_id.in_(owned_project_ids))
            .order_by(WorkTask.created_at.desc())
            .limit(30)
            .all()
        )
    else:
        tasks = []

    for t in tasks:
        worker = db.query(DigitalWorker).filter(DigitalWorker.worker_id == t.worker_id).first()
        status = t.status.value if hasattr(t.status, "value") else t.status
        if status == TaskStatus.COMPLETED.value:
            text = f"完成了「{t.title or '任务'}」"
            kind = "completed"
        elif status in (TaskStatus.RUNNING.value, TaskStatus.RECEIVED.value, TaskStatus.QUEUED.value):
            text = f"开始执行「{t.title or '任务'}」"
            kind = "running"
        elif status == TaskStatus.NEED_HUMAN.value:
            text = f"请求授权：「{t.title or '操作'}」"
            kind = "approval"
        else:
            continue
        ts = t.finished_at or t.started_at or t.created_at
        activities.append({
            "id": f"task-{t.task_id}",
            "kind": kind,
            "worker_id": t.worker_id or "",
            "worker_name": worker.name if worker else "数字员工",
            "text": text,
            "created_at": ts,
        })

    pending = db.query(Message).filter(Message.msg_type == "approval_card").order_by(
        Message.created_at.desc()
    ).limit(10).all()
    for msg in pending:
        content = msg.content or {}
        if content.get("status") != "PENDING":
            continue
        # Same ownership gate as workbench pending_approvals
        item = (
            db.query(ProjectItem).filter(ProjectItem.task_id == msg.ref_task_id).first()
            if msg.ref_task_id else None
        )
        project = (
            db.query(Project).filter(Project.project_id == item.project_id).first()
            if item else None
        )
        if not project and msg.ref_task_id:
            task_ref = db.query(WorkTask).filter(WorkTask.task_id == msg.ref_task_id).first()
            if task_ref and task_ref.project_id:
                project = db.query(Project).filter(Project.project_id == task_ref.project_id).first()
        if not project or project.owner_id != owner_id:
            continue
        worker = db.query(DigitalWorker).filter(DigitalWorker.worker_id == msg.sender_id).first()
        activities.append({
            "id": f"apr-{msg.msg_id}",
            "kind": "approval",
            "worker_id": msg.sender_id or "",
            "worker_name": worker.name if worker else "数字员工",
            "text": content.get("text") or "请求操作授权",
            "created_at": msg.created_at,
        })

    for p in projects:
        activities.append({
            "id": f"proj-{p.project_id}",
            "kind": "project",
            "worker_id": "",
            "worker_name": "",
            "text": f"{p.name}项目已创建",
            "created_at": p.created_at,
        })

    activities.sort(key=lambda a: a.get("created_at") or datetime.min, reverse=True)
    return activities[:limit]
