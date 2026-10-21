"""Seed demo workbench data: HR projects and items for office worker demo."""
from datetime import date, datetime, timedelta, timezone
from sqlalchemy.orm import Session

from models import (
    Project, ProjectItem, ProjectStatus, ProjectItemStatus,
    ProjectDocument, ProjectActivity, ProjectDocSource, ProjectOwnerType,
    DigitalWorker, WorkTask, TaskStatus, TaskSource, HumanUser, WorkerStatus,
    gen_uuid, now_utc,
)

DEMO_OWNER_ID = "u-zhang"
DEMO_MARKER = "demo-workbench-v1"


def _find_worker(db: Session, name_hint: str = "") -> DigitalWorker | None:
    q = db.query(DigitalWorker).filter(DigitalWorker.status == WorkerStatus.ON_DUTY)
    if name_hint:
        w = q.filter(DigitalWorker.name.contains(name_hint)).first()
        if w:
            return w
    return q.first()


def _find_workers(db: Session) -> list[DigitalWorker]:
    return (
        db.query(DigitalWorker)
        .filter(DigitalWorker.status == WorkerStatus.ON_DUTY)
        .order_by(DigitalWorker.name)
        .all()
    )


def _dt(year, month, day, hour=0, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc).replace(tzinfo=None)


def seed_demo_workbench(db: Session):
    existing = db.query(Project).filter(
        Project.owner_id == DEMO_OWNER_ID,
        Project.description.contains(DEMO_MARKER),
    ).first()
    if existing:
        return

    owner = db.query(HumanUser).filter(HumanUser.user_id == DEMO_OWNER_ID).first()
    if not owner:
        return

    owner.dept_id = owner.dept_id or "dept-hr"
    owner.title = "人力资源经理"
    owner.name = "张经理"

    workers = _find_workers(db)
    worker = workers[0] if workers else None
    worker_id = worker.worker_id if worker else None
    worker_name = worker.name if worker else "招聘助手"
    analyst = workers[1] if len(workers) > 1 else worker
    analyst_id = analyst.worker_id if analyst else ""
    analyst_name = analyst.name if analyst else "数据分析员"

    p1 = Project(
        project_id="proj-hr-plan",
        owner_id=DEMO_OWNER_ID,
        name="全年人力资源计划",
        description=f"年度人力资源统筹规划\n{DEMO_MARKER}",
        progress_pct=40,
        sort=1,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    p2 = Project(
        project_id="proj-campus",
        owner_id=DEMO_OWNER_ID,
        name="校园招聘",
        description=f"2026届秋季校园招聘活动\n{DEMO_MARKER}",
        progress_pct=45,
        sort=2,
        start_date=date(2026, 8, 15),
        end_date=date(2026, 10, 30),
    )
    p3 = Project(
        project_id="proj-major",
        owner_id=DEMO_OWNER_ID,
        name="大项目招聘",
        description=f"重点项目招聘管道\n{DEMO_MARKER}",
        progress_pct=80,
        sort=3,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 12, 31),
    )
    db.add_all([p1, p2, p3])

    items_campus = [
        ProjectItem(
            item_id="item-announce",
            project_id="proj-campus",
            name="招聘公告",
            status=ProjectItemStatus.COMPLETED,
            progress_pct=100,
            sort=1,
            planned_start=_dt(2026, 8, 15),
            planned_end=_dt(2026, 8, 20),
            completed_at=_dt(2026, 8, 20, 16, 0),
        ),
        ProjectItem(
            item_id="item-resume",
            project_id="proj-campus",
            name="简历筛选",
            description="2026届秋季校园招聘 — 计算机相关专业, GPA 3.5+",
            status=ProjectItemStatus.TODO,
            progress_pct=0,
            sort=2,
            worker_id=worker_id,
            planned_start=_dt(2026, 8, 21),
            planned_end=_dt(2026, 9, 10),
        ),
        ProjectItem(
            item_id="item-written",
            project_id="proj-campus",
            name="笔试",
            status=ProjectItemStatus.TODO,
            sort=3,
            planned_start=_dt(2026, 9, 15),
            planned_end=_dt(2026, 9, 18),
        ),
        ProjectItem(
            item_id="item-interview",
            project_id="proj-campus",
            name="面试",
            status=ProjectItemStatus.TODO,
            sort=4,
            planned_start=_dt(2026, 9, 25),
            planned_end=_dt(2026, 10, 15),
        ),
    ]

    resume_item = items_campus[1]
    resume_item.meta = {
        "progress_steps": [],
        "stats": {"passed": 0, "rejected": 0, "total": 156},
        "progress_note": "待委派或待确认启动",
        "intent": "筛选符合条件的校招候选人",
    }
    resume_item.task_id = None
    if worker_id:
        resume_item.worker_id = worker_id
        resume_item.status = ProjectItemStatus.DELEGATED
        resume_item.meta["delegate_instruction"] = "筛选计算机相关专业、GPA 3.5+ 的候选人"
        resume_item.meta["delegate_task_type"] = "hr.resume_screen"
        resume_item.meta["progress_note"] = "已委派，等待人工确认启动"

    db.add_all(items_campus)

    db.add_all([
        ProjectItem(
            item_id="item-plan-q1",
            project_id="proj-hr-plan",
            name="Q1 人力规划",
            status=ProjectItemStatus.IN_PROGRESS,
            progress_pct=60,
            sort=1,
            planned_start=_dt(2026, 1, 10),
            planned_end=_dt(2026, 3, 31),
        ),
        ProjectItem(
            item_id="item-plan-q2",
            project_id="proj-hr-plan",
            name="Q2 人力规划",
            status=ProjectItemStatus.TODO,
            sort=2,
            planned_start=_dt(2026, 4, 1),
            planned_end=_dt(2026, 6, 30),
        ),
        ProjectItem(
            item_id="item-major-pipeline",
            project_id="proj-major",
            name="候选人管道维护",
            status=ProjectItemStatus.TODO,
            progress_pct=0,
            sort=1,
            worker_id=worker_id,
            planned_start=_dt(2026, 6, 1),
            planned_end=_dt(2026, 11, 30),
        ),
    ])

    _seed_campus_extras(db, worker_id or "", worker_name, analyst_id, analyst_name)
    db.commit()
    print("[seed] demo workbench projects initialized for 张经理")


def _resume_progress_steps(worker_name: str = "招聘助手") -> list:
    return [
        {
            "key": "step-1",
            "title": "解析筛选条件",
            "status": "completed",
            "time_range": "14:00 - 14:02",
            "detail": "分析筛选条件：计算机相关专业、GPA 3.5+、本科及以上学历。",
            "result": "识别出 3 个筛选维度，匹配 HR 系统字段映射。",
            "tags": ["专业匹配", "GPA 筛选", "学历筛选"],
        },
        {
            "key": "step-2",
            "title": "连接 HR 系统获取简历数据",
            "status": "completed",
            "time_range": "14:02 - 14:05",
            "detail": f"通过 HR 系统 API 获取候选人简历数据，由 {worker_name} 处理。",
            "result": "156 份简历",
        },
        {
            "key": "step-3",
            "title": "第一批简历筛选 (1-30)",
            "status": "completed",
            "time_range": "14:05 - 14:12",
            "detail": "筛选第 1-30 份简历。",
            "result": "通过 22 份，淘汰 8 份。",
            "candidates": [
                {"id": "#003", "name": "陈晨", "result": "通过", "reason": "—"},
                {"id": "#007", "name": "林浩", "result": "淘汰", "reason": "GPA 3.2 不符合要求"},
            ],
        },
        {
            "key": "step-4",
            "title": "第 2 批筛选",
            "status": "running",
            "time_range": "14:12 - 进行中",
            "detail": "正在解析第 3/5 批简历…",
            "batch_progress": {"percent": 60, "done": 18, "total": 30},
        },
        {
            "key": "step-5",
            "title": "汇总结果并输出",
            "status": "pending",
            "eta": "约 12 分钟",
            "detail": "汇总通过名单并输出筛选报告。",
            "planned_outputs": ["通过名单.xlsx", "筛选报告.pdf"],
        },
    ]


def _seed_campus_extras(db: Session, worker_id: str, worker_name: str, analyst_id: str, analyst_name: str):
    """Documents + activities for campus project (idempotent by fixed IDs)."""
    docs = [
        ("doc-campus-1", "2026校招简历汇总表.xlsx", "UPLOAD", "HUMAN", DEMO_OWNER_ID, "张经理", 2_400_000),
        ("doc-campus-2", "校园招聘数据分析报告.pdf", "AI_GENERATED", "WORKER", analyst_id, analyst_name, 1_800_000),
        ("doc-campus-3", "2026秋季校园招聘公告.docx", "AI_GENERATED", "WORKER", worker_id, worker_name, 856_000),
        ("doc-campus-4", "面试评估标准与流程.pptx", "UPLOAD", "HUMAN", DEMO_OWNER_ID, "张经理", 3_200_000),
        ("doc-campus-5", "候选人评分明细表.xlsx", "AI_GENERATED", "WORKER", worker_id, worker_name, 420_000),
        ("doc-campus-6", "校园招聘项目计划书.docx", "UPLOAD", "HUMAN", DEMO_OWNER_ID, "张经理", 1_100_000),
    ]
    now = _now_utc_naive()
    offsets = [
        timedelta(minutes=40),
        timedelta(hours=1, minutes=15),
        timedelta(days=1, hours=8),
        timedelta(days=1, hours=14),
        timedelta(days=2, hours=15),
        timedelta(days=18),
    ]
    for (doc_id, name, source, owner_type, owner_id, owner_name, size), offset in zip(docs, offsets):
        if db.query(ProjectDocument).filter(ProjectDocument.doc_id == doc_id).first():
            continue
        ts = now - offset
        db.add(ProjectDocument(
            doc_id=doc_id,
            project_id="proj-campus",
            name=name,
            file_path="",
            mime_type="",
            size_bytes=size,
            source=ProjectDocSource(source),
            owner_type=ProjectOwnerType(owner_type),
            owner_id=owner_id or "",
            owner_name=owner_name or "",
            created_at=ts,
            updated_at=ts,
        ))

    activities = [
        ("act-campus-1", "progress", f"简历筛选进度更新至 80%", "WORKER", worker_id, worker_name, timedelta(minutes=10)),
        ("act-campus-2", "progress", "第2批简历筛选完成", "WORKER", worker_id, worker_name, timedelta(minutes=30)),
        ("act-campus-3", "document", "招聘数据统计报告已生成", "WORKER", analyst_id, analyst_name, timedelta(hours=1)),
        ("act-campus-4", "project", "项目创建", "HUMAN", DEMO_OWNER_ID, "张经理", timedelta(days=2)),
    ]
    for act_id, kind, text, actor_type, actor_id, actor_name, offset in activities:
        if db.query(ProjectActivity).filter(ProjectActivity.activity_id == act_id).first():
            continue
        db.add(ProjectActivity(
            activity_id=act_id,
            project_id="proj-campus",
            kind=kind,
            text=text,
            actor_type=ProjectOwnerType(actor_type),
            actor_id=actor_id or "",
            actor_name=actor_name or "",
            created_at=now - offset,
        ))


def _now_utc_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def patch_demo_workbench_v2(db: Session):
    """Backfill dates/docs/activities for existing demo DBs that skipped reseed."""
    campus = db.query(Project).filter(Project.project_id == "proj-campus").first()
    if not campus:
        return

    changed = False
    if not campus.start_date:
        campus.start_date = date(2026, 8, 15)
        campus.end_date = date(2026, 10, 30)
        if DEMO_MARKER in (campus.description or "") and "2026届" not in (campus.description or ""):
            campus.description = f"2026届秋季校园招聘活动\n{DEMO_MARKER}"
        changed = True

    item_dates = {
        "item-announce": (_dt(2026, 8, 15), _dt(2026, 8, 20), _dt(2026, 8, 20, 16, 0)),
        "item-resume": (_dt(2026, 8, 21), _dt(2026, 9, 10), None),
        "item-written": (_dt(2026, 9, 15), _dt(2026, 9, 18), None),
        "item-interview": (_dt(2026, 9, 25), _dt(2026, 10, 15), None),
    }
    for item_id, (ps, pe, ca) in item_dates.items():
        item = db.query(ProjectItem).filter(ProjectItem.item_id == item_id).first()
        if not item:
            continue
        if not item.planned_start:
            item.planned_start = ps
            item.planned_end = pe
            if ca:
                item.completed_at = ca
            changed = True
        if item_id == "item-resume":
            # Prefer pending-start state; do not re-inject fake running progress
            if item.task_id == "task-demo-resume":
                item.task_id = None
                changed = True
            meta = dict(item.meta or {})
            if not meta.get("delegate_instruction") and item.worker_id:
                meta["delegate_instruction"] = "筛选计算机相关专业、GPA 3.5+ 的候选人"
                meta["delegate_task_type"] = "hr.resume_screen"
                meta["progress_note"] = "已委派，等待人工确认启动"
                item.meta = meta
                item.status = ProjectItemStatus.DELEGATED
                changed = True
            if not item.description or "筛选计算机" in item.description:
                item.description = "2026届秋季校园招聘 — 计算机相关专业, GPA 3.5+"
                changed = True
            # Drop legacy fake running task
            legacy = db.query(WorkTask).filter(WorkTask.task_id == "task-demo-resume").first()
            if legacy:
                db.delete(legacy)
                changed = True


    workers = _find_workers(db)
    worker = workers[0] if workers else None
    analyst = workers[1] if len(workers) > 1 else worker
    worker_id = worker.worker_id if worker else ""
    worker_name = worker.name if worker else "招聘助手"
    analyst_id = analyst.worker_id if analyst else ""
    analyst_name = analyst.name if analyst else "数据分析员"

    before_docs = db.query(ProjectDocument).filter(ProjectDocument.project_id == "proj-campus").count()
    _seed_campus_extras(db, worker_id, worker_name, analyst_id, analyst_name)
    after_docs = db.query(ProjectDocument).filter(ProjectDocument.project_id == "proj-campus").count()
    if after_docs > before_docs:
        changed = True

    hr = db.query(Project).filter(Project.project_id == "proj-hr-plan").first()
    if hr and not hr.start_date:
        hr.start_date = date(2026, 1, 1)
        hr.end_date = date(2026, 12, 31)
        changed = True
    major = db.query(Project).filter(Project.project_id == "proj-major").first()
    if major and not major.start_date:
        major.start_date = date(2026, 6, 1)
        major.end_date = date(2026, 12, 31)
        changed = True

    if changed:
        db.commit()
        print("[seed] demo workbench v2 patch applied")
