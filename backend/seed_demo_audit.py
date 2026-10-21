"""Seed economic-responsibility audit project for 李四 — DELEGATED pending confirm-start."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from models import (
    Project, ProjectItem, ProjectStatus, ProjectItemStatus,
    ProjectDocument, ProjectActivity, ProjectDocSource, ProjectOwnerType,
    WorkTask, Message, HumanUser, DigitalWorker, now_utc,
)
from seed_demo_workers import WORKER_XIAOSHEN, DUTY_AUDIT_COLLECT, DUTY_AUDIT_RISK
from seed_from_vela_agent import worker_assignable

AUDIT_OWNER_ID = "u-lisi"
AUDIT_MARKER = "demo-scenarios-v3"
PROJECT_ID = "proj-audit-econ"
TASK_RISK = "task-demo-audit-risk"
TASK_COLLECT = "task-demo-audit-collect"
CONV_AUDIT = "conv-demo-audit-xiao"
MSG_AUDIT_APPROVAL = "msg-demo-audit-approval"
SESSION_AUDIT = "demo-session-audit"
APPROVAL_AUDIT = "demo-approval-audit-1"


def _dt(year, month, day, hour=0, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc).replace(tzinfo=None)


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _cleanup_fake_audit_runtime(db: Session):
    for tid in (TASK_RISK, TASK_COLLECT, "task-demo-audit-report"):
        t = db.query(WorkTask).filter(WorkTask.task_id == tid).first()
        if t:
            db.delete(t)
    msg = db.query(Message).filter(Message.msg_id == MSG_AUDIT_APPROVAL).first()
    if msg:
        db.delete(msg)
    for item in db.query(ProjectItem).filter(ProjectItem.project_id == PROJECT_ID).all():
        if item.task_id in (TASK_RISK, TASK_COLLECT, "task-demo-audit-report"):
            item.task_id = None
    db.flush()


def _assign_pending(item: ProjectItem, worker: DigitalWorker | None, instruction: str, task_type: str = ""):
    if not worker_assignable(worker):
        item.worker_id = None
        item.task_id = None
        if item.status == ProjectItemStatus.DELEGATED:
            item.status = ProjectItemStatus.TODO
        return
    item.worker_id = worker.worker_id
    item.task_id = None
    item.status = ProjectItemStatus.DELEGATED
    meta = dict(item.meta or {})
    meta["delegate_instruction"] = instruction
    meta["delegate_task_type"] = task_type
    item.meta = meta


def seed_demo_audit(db: Session):
    owner = db.query(HumanUser).filter(HumanUser.user_id == AUDIT_OWNER_ID).first()
    if not owner:
        print("[seed] skip audit: owner u-lisi missing")
        return

    _cleanup_fake_audit_runtime(db)

    worker = db.query(DigitalWorker).filter(DigitalWorker.worker_id == WORKER_XIAOSHEN).first()
    worker_id = worker.worker_id if worker else None
    worker_name = worker.name if worker else "小审"

    project = db.query(Project).filter(Project.project_id == PROJECT_ID).first()
    if not project:
        project = Project(
            project_id=PROJECT_ID,
            owner_id=AUDIT_OWNER_ID,
            name="经济责任审计",
            description=f"某单位负责人离任经济责任审计项目\n{AUDIT_MARKER}",
            status=ProjectStatus.ACTIVE,
            progress_pct=20,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 9, 30),
            sort=10,
        )
        db.add(project)
        db.flush()
    else:
        if AUDIT_MARKER not in (project.description or ""):
            project.description = f"{(project.description or '').split(chr(10))[0]}\n{AUDIT_MARKER}"
        project.status = ProjectStatus.ACTIVE

    now = _now()
    docs = [
        ("doc-audit-risk-domain", "风险域清单.md", 12_000),
        ("doc-audit-sample", "抽样核对表.xlsx", 88_000),
    ]
    for doc_id, name, size in docs:
        if db.query(ProjectDocument).filter(ProjectDocument.doc_id == doc_id).first():
            continue
        db.add(ProjectDocument(
            doc_id=doc_id,
            project_id=PROJECT_ID,
            name=name,
            size_bytes=size,
            source=ProjectDocSource.AI_GENERATED,
            owner_type=ProjectOwnerType.WORKER,
            owner_id=worker_id or "",
            owner_name=worker_name,
            created_at=now - timedelta(days=3),
            updated_at=now - timedelta(days=3),
        ))

    items_spec = [
        {
            "item_id": "item-audit-collect",
            "name": "立项资料收集",
            "description": "收集被审计单位职责、财务、合同等立项基础资料",
            "status": ProjectItemStatus.TODO,
            "progress_pct": 0,
            "sort": 1,
            "instruction": "收集被审计单位职责、财务、合同等立项基础资料",
            "task_type": "audit.material_collect",
            "planned_start": _dt(2026, 7, 1),
            "planned_end": _dt(2026, 7, 20),
            "meta": {"intent": "完成立项资料包", "progress_note": "已委派，等待人工确认启动"},
        },
        {
            "item_id": "item-audit-risk",
            "name": "风险初筛",
            "description": "对被审计对象开展风险初筛，输出高中低风险清单",
            "status": ProjectItemStatus.TODO,
            "progress_pct": 0,
            "sort": 2,
            "instruction": "对被审计对象开展风险初筛，输出高中低风险清单与初筛报告",
            "task_type": "audit.risk_scan",
            "planned_start": _dt(2026, 7, 20),
            "planned_end": _dt(2026, 8, 31),
            "meta": {
                "intent": "完成经济责任审计风险初筛",
                "progress_note": "已委派，等待人工确认启动",
                "stats": {"high": 0, "medium": 0, "low": 0, "total": 0},
            },
        },
        {
            "item_id": "item-audit-interview",
            "name": "重点访谈",
            "description": "对高风险事项相关责任人安排访谈",
            "status": ProjectItemStatus.TODO,
            "progress_pct": 0,
            "sort": 3,
            "instruction": None,
            "task_type": "",
            "planned_start": _dt(2026, 8, 20),
            "planned_end": _dt(2026, 9, 5),
            "meta": {"progress_note": "未开始"},
        },
        {
            "item_id": "item-audit-report",
            "name": "报告初稿撰写",
            "description": "基于初筛与访谈结果起草审计报告初稿",
            "status": ProjectItemStatus.TODO,
            "progress_pct": 0,
            "sort": 4,
            "instruction": None,
            "task_type": "",
            "planned_start": _dt(2026, 9, 5),
            "planned_end": _dt(2026, 9, 28),
            "meta": {"progress_note": "未开始"},
        },
    ]

    for spec in items_spec:
        item = db.query(ProjectItem).filter(ProjectItem.item_id == spec["item_id"]).first()
        if not item:
            item = ProjectItem(
                item_id=spec["item_id"],
                project_id=PROJECT_ID,
                name=spec["name"],
                description=spec["description"],
                status=spec["status"],
                progress_pct=spec["progress_pct"],
                sort=spec["sort"],
                planned_start=spec["planned_start"],
                planned_end=spec["planned_end"],
                meta=spec["meta"],
            )
            db.add(item)
            db.flush()
        else:
            item.name = spec["name"]
            item.description = spec["description"]
            item.progress_pct = spec["progress_pct"]
            item.meta = spec["meta"]
            item.planned_start = item.planned_start or spec["planned_start"]
            item.planned_end = item.planned_end or spec["planned_end"]

        if spec.get("instruction"):
            _assign_pending(item, worker, spec["instruction"], spec.get("task_type") or "")
        else:
            item.worker_id = None
            item.task_id = None
            item.status = ProjectItemStatus.TODO

    act_id = "act-audit-delegate-1"
    if not db.query(ProjectActivity).filter(ProjectActivity.activity_id == act_id).first():
        db.add(ProjectActivity(
            activity_id=act_id,
            project_id=PROJECT_ID,
            kind="delegate",
            text=f"委派「风险初筛」给{worker_name}（待确认启动）",
            actor_type=ProjectOwnerType.HUMAN,
            actor_id=AUDIT_OWNER_ID,
            actor_name=owner.name or "李四",
            created_at=now - timedelta(hours=4),
        ))

    db.commit()
    print("[seed] audit econ ready (pending-start)")
