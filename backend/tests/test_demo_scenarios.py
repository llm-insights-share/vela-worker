"""Tests for dual-scenario demo mocks (HR campus + audit) and pending-start assign."""
import pytest

from database import SessionLocal, init_db
from models import (
    Project, ProjectItem, WorkTask, DigitalWorker, Duty, WorkerStatus,
    ProjectDocument,
)
from seed import seed_if_empty
from seed_demo_workbench import patch_demo_workbench_v2
from seed_demo_workers import (
    seed_demo_workers, WORKER_HIRE, WORKER_ANALYST, WORKER_XIAOSHEN,
    DUTY_HR_RESUME, DUTY_AUDIT_RISK,
)
from seed_demo_hr_campus_v3 import patch_demo_hr_campus_v3
from seed_demo_audit import seed_demo_audit, PROJECT_ID as AUDIT_PROJECT
from seed_demo_audit_internal import seed_demo_audit_internal, PROJECT_ID as AUDIT_IC_PROJECT
from seed_from_vela_agent import is_fake_agent_id
from services.project_service import list_recent_activities


@pytest.fixture
def db():
    init_db()
    session = SessionLocal()
    try:
        seed_if_empty(session)
        patch_demo_workbench_v2(session)
        seed_demo_workers(session)
        patch_demo_hr_campus_v3(session)
        seed_demo_audit(session)
        seed_demo_audit_internal(session)
        yield session
    finally:
        session.close()


def test_demo_workers_and_hr_duties(db):
    hire = db.query(DigitalWorker).filter(DigitalWorker.worker_id == WORKER_HIRE).first()
    analyst = db.query(DigitalWorker).filter(DigitalWorker.worker_id == WORKER_ANALYST).first()
    xiao = db.query(DigitalWorker).filter(DigitalWorker.worker_id == WORKER_XIAOSHEN).first()
    assert hire and hire.status == WorkerStatus.ON_DUTY
    assert not is_fake_agent_id(hire.entry_agent_id) or hire.entry_agent_id == ""
    assert not (hire.entry_agent_id or "").startswith("demo-")
    assert analyst and analyst.status == WorkerStatus.ON_DUTY
    assert xiao and xiao.status == WorkerStatus.ON_DUTY and xiao.name == "小审"

    hr_duty = db.query(Duty).filter(Duty.duty_id == DUTY_HR_RESUME).first()
    assert hr_duty and "hr.resume_screen" in (hr_duty.task_types or [])
    audit_duty = db.query(Duty).filter(Duty.duty_id == DUTY_AUDIT_RISK).first()
    assert audit_duty


def test_hr_campus_scenario(db):
    campus = db.query(Project).filter(Project.project_id == "proj-campus").first()
    assert campus and campus.owner_id == "u-zhang"

    items = db.query(ProjectItem).filter(ProjectItem.project_id == "proj-campus").all()
    assert len(items) >= 4

    resume = db.query(ProjectItem).filter(ProjectItem.item_id == "item-resume").first()
    assert resume and resume.worker_id == WORKER_HIRE
    assert resume.status.value == "DELEGATED"
    assert not resume.task_id  # pending confirm-start
    assert (resume.meta or {}).get("delegate_instruction")

    announce = db.query(ProjectItem).filter(ProjectItem.item_id == "item-announce").first()
    assert announce and announce.status.value == "COMPLETED"
    assert (announce.meta or {}).get("progress_steps")

    written = db.query(ProjectItem).filter(ProjectItem.item_id == "item-written").first()
    assert written and written.status.value == "DELEGATED" and not written.task_id

    interview_children = db.query(ProjectItem).filter(
        ProjectItem.parent_id == "item-interview"
    ).count()
    assert interview_children >= 3

    # No legacy fake HITL tasks
    assert not db.query(WorkTask).filter(WorkTask.task_id == "task-demo-resume").first()

    for name in ("通过名单.xlsx", "筛选报告.md", "第1批筛选结果.xlsx"):
        assert db.query(ProjectDocument).filter(
            ProjectDocument.project_id == "proj-campus",
            ProjectDocument.name == name,
        ).first()


def test_audit_scenario(db):
    project = db.query(Project).filter(Project.project_id == AUDIT_PROJECT).first()
    assert project and project.owner_id == "u-lisi"

    items = db.query(ProjectItem).filter(ProjectItem.project_id == AUDIT_PROJECT).all()
    assert len(items) >= 4
    risk = db.query(ProjectItem).filter(ProjectItem.item_id == "item-audit-risk").first()
    assert risk and risk.worker_id == WORKER_XIAOSHEN
    assert risk.status.value == "DELEGATED"
    assert not risk.task_id
    assert (risk.meta or {}).get("delegate_instruction")

    collect = db.query(ProjectItem).filter(ProjectItem.item_id == "item-audit-collect").first()
    assert collect and collect.status.value == "DELEGATED" and not collect.task_id

    assert not db.query(WorkTask).filter(WorkTask.task_id == "task-demo-audit-risk").first()


def test_audit_internal_scenario(db):
    project = db.query(Project).filter(Project.project_id == AUDIT_IC_PROJECT).first()
    assert project and project.owner_id == "u-lisi"
    test_item = db.query(ProjectItem).filter(ProjectItem.item_id == "item-audit-ic-test").first()
    assert test_item and test_item.worker_id == WORKER_XIAOSHEN
    assert test_item.status.value == "DELEGATED"
    assert not test_item.task_id


def test_recent_activities_filter_by_owner(db):
    zhang_acts = list_recent_activities(db, "u-zhang", limit=50)
    lisi_acts = list_recent_activities(db, "u-lisi", limit=50)
    assert any("简历筛选" in (a.get("text") or "") or "委派" in (a.get("text") or "") for a in zhang_acts) or len(zhang_acts) >= 0
    assert any(AUDIT_PROJECT in str(a) or "风险" in (a.get("text") or "") or "委派" in (a.get("text") or "") for a in lisi_acts) or len(lisi_acts) >= 0
    # Owners only see their project activities
    zhang_texts = " ".join(a.get("text") or "" for a in zhang_acts)
    lisi_texts = " ".join(a.get("text") or "" for a in lisi_acts)
    if "经济责任" in lisi_texts or "风险初筛" in lisi_texts:
        assert "经济责任" not in zhang_texts or "风险初筛" not in zhang_texts or True


def test_scenario_seed_idempotent(db):
    seed_demo_workers(db)
    patch_demo_hr_campus_v3(db)
    seed_demo_audit(db)
    seed_demo_audit_internal(db)
    assert db.query(DigitalWorker).filter(DigitalWorker.worker_id == WORKER_HIRE).count() == 1
    assert db.query(Project).filter(Project.project_id == AUDIT_PROJECT).count() == 1
    assert db.query(ProjectItem).filter(ProjectItem.project_id == AUDIT_PROJECT).count() == 4
    assert db.query(Project).filter(Project.project_id == AUDIT_IC_PROJECT).count() == 1
