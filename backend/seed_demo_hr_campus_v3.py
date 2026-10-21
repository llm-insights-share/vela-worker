"""Patch HR campus project: bind real workers, DELEGATED pending confirm-start (no fake sessions)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from models import (
    Project, ProjectItem, ProjectItemStatus, ProjectDocument, ProjectActivity,
    ProjectDocSource, ProjectOwnerType, WorkTask, Message, DigitalWorker,
)
from seed_demo_workers import WORKER_HIRE, WORKER_ANALYST, DUTY_HR_ANNOUNCE
from seed_demo_workbench import DEMO_OWNER_ID, DEMO_MARKER, _dt, _now_utc_naive
from seed_from_vela_agent import worker_assignable

SCENARIO_MARKER = "demo-scenarios-v3"
# Legacy constants kept for tests that import names (no longer seed fake HITL)
CONV_HR_HIRE = "conv-demo-hr-hire"
MSG_HR_APPROVAL = "msg-demo-hr-approval"
TASK_RESUME = "task-demo-resume"
SESSION_HR = "demo-session-hr"
APPROVAL_HR = "demo-approval-hr-1"


def _cleanup_fake_hr_runtime(db: Session):
    """Remove demo-session / demo-task HITL artifacts from older seeds."""
    fake_task_ids = [
        TASK_RESUME, "task-demo-announce", "task-demo-written",
        "task-demo-major-pipeline",
    ]
    for tid in fake_task_ids:
        t = db.query(WorkTask).filter(WorkTask.task_id == tid).first()
        if t:
            db.delete(t)
    msg = db.query(Message).filter(Message.msg_id == MSG_HR_APPROVAL).first()
    if msg:
        db.delete(msg)
    # Clear item.task_id pointing at deleted tasks
    for item in db.query(ProjectItem).filter(ProjectItem.project_id.in_(["proj-campus", "proj-major"])).all():
        if item.task_id in fake_task_ids:
            item.task_id = None
        # Drop NEED_HUMAN showcase meta that depended on fake session
        meta = dict(item.meta or {})
        if meta.pop("pending_approval_id", None) or meta.pop("demo_session_id", None):
            item.meta = meta
    db.flush()


def _ensure_artifact_docs(db: Session, hire_id: str, hire_name: str) -> dict:
    docs_spec = [
        ("doc-campus-batch1", "第1批筛选结果.xlsx", 180_000),
        ("doc-campus-passlist", "通过名单.xlsx", 96_000),
        ("doc-campus-screen-report", "筛选报告.md", 42_000),
        ("doc-campus-announce", "校招公告终稿.md", 28_000),
    ]
    now = _now_utc_naive()
    out = {}
    for doc_id, name, size in docs_spec:
        doc = db.query(ProjectDocument).filter(ProjectDocument.doc_id == doc_id).first()
        if not doc:
            doc = ProjectDocument(
                doc_id=doc_id,
                project_id="proj-campus",
                name=name,
                file_path="",
                mime_type="",
                size_bytes=size,
                source=ProjectDocSource.AI_GENERATED,
                owner_type=ProjectOwnerType.WORKER,
                owner_id=hire_id or "",
                owner_name=hire_name or "",
                created_at=now - timedelta(hours=2),
                updated_at=now - timedelta(hours=2),
            )
            db.add(doc)
            db.flush()
        out[name] = {"doc_id": doc.doc_id, "path": doc.file_path or "", "name": name}
    return out


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


def _enrich_announce_completed(db: Session, hire: DigitalWorker | None, hire_name: str):
    item = db.query(ProjectItem).filter(ProjectItem.item_id == "item-announce").first()
    if not item:
        return
    item.name = "招聘公告"
    item.status = ProjectItemStatus.COMPLETED
    item.progress_pct = 100
    item.worker_id = hire.worker_id if worker_assignable(hire) else item.worker_id
    item.task_id = None  # showcase via meta only — no fake WorkTask
    item.completed_at = item.completed_at or _dt(2026, 8, 20, 16, 0)
    item.description = "起草并发布 2026 届校招公告"
    item.meta = {
        "intent": "完成校招公告撰写与发布",
        "progress_note": "已完成",
        "progress_steps": [
            {
                "key": "step-1",
                "title": "起草招聘公告",
                "status": "completed",
                "duty_id": DUTY_HR_ANNOUNCE,
                "duty_name": "招聘公告撰写",
                "agent_name": hire_name,
                "detail": "完成岗位描述与投递渠道文案。",
                "result": "公告终稿已定稿",
            },
            {
                "key": "step-2",
                "title": "发布公告",
                "status": "completed",
                "duty_name": "招聘公告撰写",
                "agent_name": hire_name,
                "detail": "发布至官网与校招渠道。",
                "result": "已发布",
            },
        ],
        "artifacts": [{"name": "校招公告终稿.md"}],
    }


def _enrich_interview_tree(db: Session):
    parent = db.query(ProjectItem).filter(ProjectItem.item_id == "item-interview").first()
    if not parent:
        return
    parent.name = "面试组织"
    parent.status = ProjectItemStatus.TODO
    parent.progress_pct = 0
    parent.worker_id = None
    parent.task_id = None
    parent.description = "组织通过笔试候选人的多轮面试"
    parent.meta = {
        "intent": "完成一面/二面/HR 面安排",
        "progress_note": "等待笔试结果后启动",
    }
    children = [
        ("item-interview-r1", "技术一面", 1, "初筛技术能力与项目经验"),
        ("item-interview-r2", "技术二面", 2, "深度评估系统设计与协作"),
        ("item-interview-hr", "HR 终面", 3, "文化匹配与薪酬沟通"),
    ]
    for item_id, name, sort, desc in children:
        child = db.query(ProjectItem).filter(ProjectItem.item_id == item_id).first()
        if not child:
            db.add(ProjectItem(
                item_id=item_id,
                project_id="proj-campus",
                parent_id="item-interview",
                name=name,
                description=desc,
                status=ProjectItemStatus.TODO,
                progress_pct=0,
                sort=sort,
                worker_id=None,
                meta={"intent": desc},
                planned_start=_dt(2026, 9, 8 + sort),
                planned_end=_dt(2026, 9, 15 + sort),
            ))
        else:
            child.parent_id = "item-interview"
            child.name = name
            child.status = ProjectItemStatus.TODO
            child.task_id = None
            child.worker_id = None


def patch_demo_hr_campus_v3(db: Session):
    """Campus project: completed announce + pending-start delegated items for real workers."""
    campus = db.query(Project).filter(Project.project_id == "proj-campus").first()
    if not campus:
        from seed_demo_workbench import seed_demo_workbench
        seed_demo_workbench(db)
        campus = db.query(Project).filter(Project.project_id == "proj-campus").first()
        if not campus:
            return

    _cleanup_fake_hr_runtime(db)

    hire = db.query(DigitalWorker).filter(DigitalWorker.worker_id == WORKER_HIRE).first()
    analyst = db.query(DigitalWorker).filter(DigitalWorker.worker_id == WORKER_ANALYST).first()
    hire_name = hire.name if hire else "招聘助手"

    if SCENARIO_MARKER not in (campus.description or ""):
        campus.description = (
            "2026届秋季校园招聘活动：覆盖公告发布、简历筛选、笔试与面试全流程。\n"
            f"{DEMO_MARKER}\n{SCENARIO_MARKER}"
        )
    campus.progress_pct = max(campus.progress_pct or 0, 35)
    campus.start_date = campus.start_date or date(2026, 8, 1)
    campus.end_date = campus.end_date or date(2026, 10, 31)

    hire_id = hire.worker_id if hire else ""
    _ensure_artifact_docs(db, hire_id, hire_name)
    _enrich_announce_completed(db, hire, hire_name)
    _enrich_interview_tree(db)

    resume = db.query(ProjectItem).filter(ProjectItem.item_id == "item-resume").first()
    if resume:
        resume.description = "2026届秋季校园招聘 — 计算机相关专业, GPA 3.5+"
        resume.progress_pct = 0
        resume.meta = {
            "intent": "筛选符合条件的校招候选人",
            "progress_note": "已委派，等待人工确认启动",
            "stats": {"passed": 0, "rejected": 0, "total": 156},
        }
        _assign_pending(
            resume, hire,
            "筛选计算机相关专业、GPA 3.5+ 的候选人",
            "hr.resume_screen",
        )

    written = db.query(ProjectItem).filter(ProjectItem.item_id == "item-written").first()
    if written:
        written.name = "笔试安排"
        written.description = "安排笔试场次并生成准考证"
        written.progress_pct = 0
        written.meta = {
            "intent": "完成笔试排期",
            "progress_note": "已委派，等待人工确认启动",
        }
        _assign_pending(written, hire, "安排笔试场次并生成准考证", "hr.written")

    major = db.query(ProjectItem).filter(ProjectItem.item_id == "item-major-pipeline").first()
    if major:
        major.progress_pct = 0
        major.meta = {"progress_note": "已委派，等待人工确认启动"}
        _assign_pending(major, hire, "维护大项目招聘候选人管道并定期更新状态", "hr.pipeline")

    # Soft-mark secondary projects
    for pid, label in (
        ("proj-hr-plan", "全年人力资源计划（次要演示）"),
        ("proj-major", "大项目招聘（次要演示）"),
    ):
        p = db.query(Project).filter(Project.project_id == pid).first()
        if p and SCENARIO_MARKER not in (p.description or ""):
            base = (p.description or label).split("\n")[0]
            p.description = f"{base}\n{DEMO_MARKER}\n{SCENARIO_MARKER}"

    now = _now_utc_naive()
    acts = [
        ("act-campus-v3-2", "completed", "「招聘公告」已完成", ProjectOwnerType.WORKER, hire_id, hire_name, timedelta(days=12)),
        ("act-campus-v3-3", "delegate", "委派「简历筛选」给招聘助手（待确认启动）", ProjectOwnerType.HUMAN, DEMO_OWNER_ID, "张经理", timedelta(hours=6)),
    ]
    for act_id, kind, text, atype, aid, aname, offset in acts:
        if db.query(ProjectActivity).filter(ProjectActivity.activity_id == act_id).first():
            continue
        db.add(ProjectActivity(
            activity_id=act_id,
            project_id="proj-campus",
            kind=kind,
            text=text,
            actor_type=atype,
            actor_id=aid or "",
            actor_name=aname or "",
            created_at=now - offset,
        ))

    db.commit()
    print(f"[seed] HR campus patched (pending-start delegated, no fake sessions)")
