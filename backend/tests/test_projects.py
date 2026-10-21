"""Tests for project / workbench API."""
import pytest
from fastapi.testclient import TestClient

from database import SessionLocal, init_db
from main import app
from models import (
    Project, ProjectItem, ProjectItemStatus, HumanUser,
    DigitalRole, DigitalWorker, RoleStatus, WorkerStatus, gen_uuid,
    Duty, WorkerDutyAgent, WorkerDutyStatus,
    ProjectDocument, ProjectActivity,
)
from security import create_access_token, hash_password

client = TestClient(app)


@pytest.fixture
def db():
    init_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _admin_headers(db):
    admin = db.query(HumanUser).filter(HumanUser.username == "admin").first()
    if not admin:
        admin = HumanUser(
            user_id="u-admin-test",
            username="admin",
            email="admin@test.local",
            hashed_password=hash_password("admin123"),
            name="Admin",
            status="ACTIVE",
        )
        db.add(admin)
        db.commit()
    token = create_access_token("admin")
    return {"Authorization": f"Bearer {token}"}


def _ensure_worker(db):
    existing = db.query(DigitalWorker).filter(DigitalWorker.status == WorkerStatus.ON_DUTY).first()
    if existing and existing.entry_agent_id:
        duty_link = db.query(WorkerDutyAgent).filter(WorkerDutyAgent.worker_id == existing.worker_id).first()
        if duty_link:
            return existing
    role_id = f"role_{gen_uuid()[:8]}"
    db.add(DigitalRole(
        role_id=role_id,
        name=f"Test Role {gen_uuid()[:6]}",
        status=RoleStatus.ACTIVE,
    ))
    worker = DigitalWorker(
        worker_id=gen_uuid(),
        employee_no=f"T{gen_uuid()[:6]}",
        name="测试助手",
        role_id=role_id,
        entry_agent_id="agent-test",
        status=WorkerStatus.ON_DUTY,
    )
    db.add(worker)
    db.flush()
    duty = db.query(Duty).first()
    if duty:
        db.add(WorkerDutyAgent(
            worker_id=worker.worker_id,
            duty_id=duty.duty_id,
            agent_id="agent-test",
            is_primary=True,
            status=WorkerDutyStatus.ACTIVE,
        ))
    db.commit()
    db.refresh(worker)
    return worker


def _cleanup_project(db, project_id):
    db.query(ProjectItem).filter(ProjectItem.project_id == project_id).delete()
    db.query(ProjectDocument).filter(ProjectDocument.project_id == project_id).delete()
    db.query(ProjectActivity).filter(ProjectActivity.project_id == project_id).delete()
    db.query(Project).filter(Project.project_id == project_id).delete()
    db.commit()


def test_project_crud_and_items(db):
    headers = _admin_headers(db)
    admin = db.query(HumanUser).filter(HumanUser.username == "admin").first()

    r = client.post("/api/v1/projects", json={"name": "测试项目", "description": "unit test"}, headers=headers)
    assert r.status_code == 201
    project_id = r.json()["project_id"]
    assert r.json()["owner_id"] == admin.user_id

    r = client.get("/api/v1/projects", headers=headers)
    assert r.status_code == 200
    assert any(p["project_id"] == project_id for p in r.json()["items"])

    r = client.post(
        f"/api/v1/projects/{project_id}/items",
        json={"name": "子事项 A"},
        headers=headers,
    )
    assert r.status_code == 201
    item_id = r.json()["item_id"]

    r = client.get(f"/api/v1/projects/{project_id}/items", headers=headers)
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1

    r = client.patch(
        f"/api/v1/projects/items/{item_id}",
        json={"status": "IN_PROGRESS", "progress_pct": 50},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["progress_pct"] == 50

    _cleanup_project(db, project_id)


def test_delegate_defaults_to_pending_start(db):
    headers = _admin_headers(db)
    worker = _ensure_worker(db)
    admin = db.query(HumanUser).filter(HumanUser.username == "admin").first()

    project = Project(owner_id=admin.user_id, name="委派测试", description="test")
    db.add(project)
    db.flush()
    item = ProjectItem(project_id=project.project_id, name="待委派事项", status=ProjectItemStatus.TODO)
    db.add(item)
    db.commit()

    r = client.post(
        f"/api/v1/projects/items/{item.item_id}/delegate",
        json={"worker_id": worker.worker_id, "instruction": "请完成测试任务"},
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["task"] is None
    assert body["item"]["status"] == "DELEGATED"
    assert body["item"]["worker_id"] == worker.worker_id
    assert not body["item"].get("task_id")
    assert body["conv_id"]
    assert (body["item"].get("meta") or {}).get("delegate_instruction") == "请完成测试任务"

    _cleanup_project(db, project.project_id)


def test_delegate_auto_start_creates_task(db):
    headers = _admin_headers(db)
    worker = _ensure_worker(db)
    admin = db.query(HumanUser).filter(HumanUser.username == "admin").first()

    project = Project(owner_id=admin.user_id, name="委派自动启动", description="test")
    db.add(project)
    db.flush()
    item = ProjectItem(project_id=project.project_id, name="立即执行事项", status=ProjectItemStatus.TODO)
    db.add(item)
    db.commit()

    r = client.post(
        f"/api/v1/projects/items/{item.item_id}/delegate",
        json={
            "worker_id": worker.worker_id,
            "instruction": "请完成测试任务",
            "auto_start": True,
        },
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["task"]["task_id"]
    assert body["item"]["status"] in ("DELEGATED", "IN_PROGRESS")
    assert body["item"]["task_id"] == body["task"]["task_id"]

    _cleanup_project(db, project.project_id)


def test_start_item_after_delegate(db):
    headers = _admin_headers(db)
    worker = _ensure_worker(db)
    admin = db.query(HumanUser).filter(HumanUser.username == "admin").first()

    project = Project(owner_id=admin.user_id, name="确认启动测试", description="test")
    db.add(project)
    db.flush()
    item = ProjectItem(project_id=project.project_id, name="待启动事项", status=ProjectItemStatus.TODO)
    db.add(item)
    db.commit()

    r = client.post(
        f"/api/v1/projects/items/{item.item_id}/delegate",
        json={"worker_id": worker.worker_id, "instruction": "启动前指令"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["task"] is None

    r = client.post(
        f"/api/v1/projects/items/{item.item_id}/start",
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["task"]["task_id"]
    assert body["item"]["task_id"] == body["task"]["task_id"]

    # Idempotent
    r2 = client.post(
        f"/api/v1/projects/items/{item.item_id}/start",
        headers=headers,
    )
    assert r2.status_code == 200
    assert r2.json()["task"]["task_id"] == body["task"]["task_id"]

    _cleanup_project(db, project.project_id)


def test_workbench_endpoint(db):
    headers = _admin_headers(db)

    r = client.get("/api/v1/projects/workbench", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "projects" in data
    assert "workers" in data
    assert "pending_approvals" in data


def test_project_members_documents_activities(db):
    headers = _admin_headers(db)

    r = client.post(
        "/api/v1/projects",
        json={"name": "详情扩展项目", "description": "tab apis"},
        headers=headers,
    )
    assert r.status_code == 201
    project_id = r.json()["project_id"]
    assert r.json().get("owner")

    r = client.get(f"/api/v1/projects/{project_id}/members", headers=headers)
    assert r.status_code == 200
    members = r.json()["items"]
    assert len(members) >= 1
    assert members[0]["tag"] == "项目负责人"

    r = client.get(f"/api/v1/projects/{project_id}/activities", headers=headers)
    assert r.status_code == 200
    assert any(a["text"] == "项目创建" for a in r.json()["items"])

    files = {"file": ("note.txt", b"hello project doc", "text/plain")}
    r = client.post(f"/api/v1/projects/{project_id}/documents", files=files, headers=headers)
    assert r.status_code == 201
    assert r.json()["name"] == "note.txt"
    assert r.json()["source"] == "UPLOAD"

    r = client.get(f"/api/v1/projects/{project_id}/documents", headers=headers)
    assert r.status_code == 200
    assert len(r.json()["items"]) >= 1

    _cleanup_project(db, project_id)