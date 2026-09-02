"""Tests for inbox (站内信) service and API."""
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from database import SessionLocal, init_db
from main import app
from models import (
    DigitalRole,
    DigitalWorker,
    InboxMessage,
    RoleStatus,
    TaskSource,
    TaskStatus,
    WorkTask,
    WorkerStatus,
    gen_uuid,
)
from security import create_access_token
from services.inbox import (
    mark_read,
    mark_read_by_task,
    notify_user,
    notify_work_task,
    unread_count,
)


@pytest.fixture
def db():
    init_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _cleanup_inbox(db, user_id: str):
    db.query(InboxMessage).filter(InboxMessage.user_id == user_id).delete()
    db.commit()


def _make_worker(db, *, worker_id: str = None, escalation_user_id: str = ""):
    role_id = f"role_{gen_uuid()[:8]}"
    db.add(
        DigitalRole(
            role_id=role_id,
            name=f"测试角色_{gen_uuid()[:6]}",
            status=RoleStatus.ACTIVE,
        )
    )
    worker = DigitalWorker(
        worker_id=worker_id or gen_uuid(),
        employee_no=f"E{datetime.now().timestamp():.0f}"[-10:],
        name="测试员工",
        role_id=role_id,
        entry_agent_id="agent-test",
        escalation_contact={"user_id": escalation_user_id} if escalation_user_id else {},
        status=WorkerStatus.ON_DUTY,
    )
    db.add(worker)
    db.commit()
    db.refresh(worker)
    return worker


def _make_task(db, worker: DigitalWorker, *, reporter_user_id: str, conv_id: str = ""):
    task = WorkTask(
        task_id=gen_uuid(),
        worker_id=worker.worker_id,
        source=TaskSource.IM,
        title="测试任务",
        instruction="do something",
        status=TaskStatus.RUNNING,
        conv_id=conv_id or None,
        reporter={"type": "HUMAN", "user_id": reporter_user_id, "name": "Reporter"},
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def test_notify_user_dedup_by_related_id(db):
    user_id = f"user_dedup_{gen_uuid()[:8]}"
    related_id = f"task_{datetime.now().timestamp()}"
    try:
        first = notify_user(
            db,
            user_id=user_id,
            title="任务已完成",
            body="demo",
            related_type="work_task",
            related_id=related_id,
        )
        second = notify_user(
            db,
            user_id=user_id,
            title="任务已完成",
            body="demo again",
            related_type="work_task",
            related_id=related_id,
        )
        assert first is not None
        assert second is not None
        assert first.message_id == second.message_id
        count = (
            db.query(InboxMessage)
            .filter(InboxMessage.user_id == user_id, InboxMessage.related_id == related_id)
            .count()
        )
        assert count == 1
    finally:
        _cleanup_inbox(db, user_id)


def test_notify_work_task_creates_message_with_status_in_related_id(db):
    reporter_id = f"user_reporter_{gen_uuid()[:8]}"
    worker = _make_worker(db)
    task = _make_task(db, worker, reporter_user_id=reporter_id, conv_id="conv-123")
    try:
        msgs = notify_work_task(db, task, worker, status=TaskStatus.COMPLETED)
        assert len(msgs) == 1
        msg = msgs[0]
        assert msg.user_id == reporter_id
        assert msg.related_type == "work_task"
        assert msg.related_id == f"{task.task_id}:COMPLETED"
        assert msg.link_path == "/im?conv=conv-123"
        assert "测试员工" in msg.body
    finally:
        _cleanup_inbox(db, reporter_id)
        db.query(WorkTask).filter(WorkTask.task_id == task.task_id).delete()
        db.query(DigitalWorker).filter(DigitalWorker.worker_id == worker.worker_id).delete()
        db.query(DigitalRole).filter(DigitalRole.role_id == worker.role_id).delete()
        db.commit()


def test_notify_work_task_need_human_notifies_escalation_contact(db):
    reporter_id = f"user_reporter_{gen_uuid()[:8]}"
    esc_id = f"user_esc_{gen_uuid()[:8]}"
    worker = _make_worker(db, escalation_user_id=esc_id)
    task = _make_task(db, worker, reporter_user_id=reporter_id)
    try:
        msgs = notify_work_task(db, task, worker, status=TaskStatus.NEED_HUMAN)
        user_ids = {m.user_id for m in msgs}
        assert reporter_id in user_ids
        assert esc_id in user_ids
        assert len(msgs) == 2
    finally:
        _cleanup_inbox(db, reporter_id)
        _cleanup_inbox(db, esc_id)
        db.query(WorkTask).filter(WorkTask.task_id == task.task_id).delete()
        db.query(DigitalWorker).filter(DigitalWorker.worker_id == worker.worker_id).delete()
        db.query(DigitalRole).filter(DigitalRole.role_id == worker.role_id).delete()
        db.commit()


def test_mark_read_and_mark_read_by_task(db):
    user_id = f"user_read_{gen_uuid()[:8]}"
    task_id = gen_uuid()
    try:
        notify_user(
            db,
            user_id=user_id,
            title="任务待审批",
            related_type="work_task",
            related_id=f"{task_id}:NEED_HUMAN",
        )
        notify_user(
            db,
            user_id=user_id,
            title="任务已完成",
            related_type="work_task",
            related_id=f"{task_id}:COMPLETED",
        )
        assert unread_count(db, user_id=user_id) == 2

        first = db.query(InboxMessage).filter(InboxMessage.user_id == user_id).first()
        marked = mark_read(db, user_id=user_id, message_id=first.message_id)
        assert marked is not None
        assert marked.is_read is True
        assert unread_count(db, user_id=user_id) == 1

        count = mark_read_by_task(db, user_id=user_id, task_id=task_id)
        assert count == 1
        assert unread_count(db, user_id=user_id) == 0
    finally:
        _cleanup_inbox(db, user_id)


def test_inbox_api_endpoints():
    init_db()
    client = TestClient(app)
    token = create_access_token("admin")
    headers = {"Authorization": f"Bearer {token}"}

    unread_res = client.get("/api/v1/inbox/unread-count", headers=headers)
    assert unread_res.status_code == 200
    assert "unread_count" in unread_res.json()

    list_res = client.get("/api/v1/inbox/messages", headers=headers)
    assert list_res.status_code == 200
    body = list_res.json()
    assert "items" in body
    assert "total" in body

    missing = client.post("/api/v1/inbox/messages/nonexistent/read", headers=headers)
    assert missing.status_code == 404

    unauth = client.get("/api/v1/inbox/unread-count")
    assert unauth.status_code == 401
