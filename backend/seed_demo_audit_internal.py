"""Seed internal-control audit project for 李四 — DELEGATED pending confirm-start."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from models import (
    Project, ProjectItem, ProjectStatus, ProjectItemStatus,
    ProjectDocument, ProjectActivity, ProjectDocSource, ProjectOwnerType,
    WorkTask, Message, HumanUser, DigitalWorker,
)
from seed_demo_workers import WORKER_XIAOSHEN
from seed_from_vela_agent import worker_assignable

AUDIT_OWNER_ID = "u-lisi"
PROJECT_ID = "proj-audit-internal"
MARKER = "demo-scenarios-v3"
TASK_TEST = "task-demo-audit-control-test"
CONV_ID = "conv-demo-audit-internal"
MSG_APPROVAL = "msg-demo-audit-internal-approval"
SESSION_ID = "demo-session-audit-internal"
APPROVAL_ID = "demo-approval-audit-internal-1"


def _dt(year, month, day, hour=0, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc).replace(tzinfo=None)


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _cleanup_fake(db: Session):
    for tid in (TASK_TEST, "task-demo-audit-ic-scope"):
        t = db.query(WorkTask).filter(WorkTask.task_id == tid).first()
        if t:
            db.delete(t)
    msg = db.query(Message).filter(Message.msg_id == MSG_APPROVAL).first()
    if msg:
        db.delete(msg)
    for item in db.query(ProjectItem).filter(ProjectItem.project_id == PROJECT_ID).all():
        if item.task_id in (TASK_TEST, "task-demo-audit-ic-scope"):
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


def seed_demo_audit_internal(db: Session):
    owner = db.query(HumanUser).filter(HumanUser.user_id == AUDIT_OWNER_ID).first()
    if not owner:
        print("[seed] skip internal audit: owner u-lisi missing")
        return

    _cleanup_fake(db)

    worker = db.query(DigitalWorker).filter(DigitalWorker.worker_id == WORKER_XIAOSHEN).first()
    worker_id = worker.worker_id if worker else None
    worker_name = worker.name if worker else "小审"

    project = db.query(Project).filter(Project.project_id == PROJECT_ID).first()
    if not project:
        project = Project(
            project_id=PROJECT_ID,
            owner_id=AUDIT_OWNER_ID,
            name="内控有效性审计",
            description=f"采购-付款循环关键控制有效性测试\n{MARKER}",
            status=ProjectStatus.ACTIVE,
            progress_pct=15,
            start_date=date(2026, 8, 1),
            end_date=date(2026, 10, 15),
            sort=11,
        )
        db.add(project)
        db.flush()
    else:
        if MARKER not in (project.description or ""):
            project.description = f"{(project.description or '').split(chr(10))[0]}\n{MARKER}"
        project.status = ProjectStatus.ACTIVE

    now = _now()
    if not db.query(ProjectDocument).filter(ProjectDocument.doc_id == "doc-audit-ic-matrix").first():
        db.add(ProjectDocument(
            doc_id="doc-audit-ic-matrix",
            project_id=PROJECT_ID,
            name="关键控制矩阵.xlsx",
            size_bytes=64_000,
            source=ProjectDocSource.UPLOAD,
            owner_type=ProjectOwnerType.HUMAN,
            owner_id=AUDIT_OWNER_ID,
            owner_name=owner.name or "李四",
            created_at=now - timedelta(days=5),
            updated_at=now - timedelta(days=5),
        ))

    items_spec = [
        {
            "item_id": "item-audit-ic-scope",
            "name": "审计范围确认",
            "description": "确认内控审计范围与关键控制矩阵",
            "sort": 1,
            "instruction": "确认内控审计范围与关键控制矩阵",
            "task_type": "audit.scope",
            "planned_start": _dt(2026, 8, 1),
            "planned_end": _dt(2026, 8, 10),
            "meta": {"intent": "锁定审计范围", "progress_note": "已委派，等待人工确认启动"},
        },
        {
            "item_id": "item-audit-ic-test",
            "name": "关键控制测试",
            "description": "执行关键控制测试并输出缺陷清单",
            "sort": 2,
            "instruction": "执行关键控制测试并输出缺陷清单",
            "task_type": "audit.control_test",
            "planned_start": _dt(2026, 8, 10),
            "planned_end": _dt(2026, 9, 15),
            "meta": {
                "intent": "完成关键控制测试",
                "progress_note": "已委派，等待人工确认启动",
                "stats": {"high": 0, "medium": 0, "low": 0, "total": 0},
            },
        },
        {
            "item_id": "item-audit-ic-followup",
            "name": "缺陷整改跟踪",
            "description": "跟踪控制缺陷整改闭环",
            "sort": 3,
            "instruction": None,
            "task_type": "",
            "planned_start": _dt(2026, 9, 15),
            "planned_end": _dt(2026, 10, 5),
            "meta": {"progress_note": "未开始"},
        },
        {
            "item_id": "item-audit-ic-report",
            "name": "内控审计报告",
            "description": "汇总测试结论并形成内控有效性报告初稿",
            "sort": 4,
            "instruction": None,
            "task_type": "",
            "planned_start": _dt(2026, 9, 20),
            "planned_end": _dt(2026, 10, 15),
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
                status=ProjectItemStatus.TODO,
                progress_pct=0,
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
            item.progress_pct = 0
            item.meta = spec["meta"]
            item.planned_start = item.planned_start or spec["planned_start"]
            item.planned_end = item.planned_end or spec["planned_end"]

        if spec.get("instruction"):
            _assign_pending(item, worker, spec["instruction"], spec.get("task_type") or "")
        else:
            item.worker_id = None
            item.task_id = None
            item.status = ProjectItemStatus.TODO

    act_id = "act-audit-ic-delegate-1"
    if not db.query(ProjectActivity).filter(ProjectActivity.activity_id == act_id).first():
        db.add(ProjectActivity(
            activity_id=act_id,
            project_id=PROJECT_ID,
            kind="delegate",
            text=f"委派「关键控制测试」给{worker_name}（待确认启动）",
            actor_type=ProjectOwnerType.HUMAN,
            actor_id=AUDIT_OWNER_ID,
            actor_name=owner.name or "李四",
            created_at=now - timedelta(hours=3),
        ))

    db.commit()
    print("[seed] audit internal ready (pending-start)")
