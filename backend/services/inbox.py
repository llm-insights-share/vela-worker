from __future__ import annotations

from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import DigitalWorker, InboxMessage, TaskStatus, WorkTask, now_utc

_TASK_STATUS_NOTIFY = {
    TaskStatus.NEED_HUMAN: ("任务待审批", "info"),
    TaskStatus.COMPLETED: ("任务已完成", "success"),
    TaskStatus.FAILED: ("任务失败", "warning"),
}


def notify_user(
    db: Session,
    *,
    user_id: str,
    title: str,
    body: str = "",
    level: str = "info",
    link_path: str = "",
    related_type: str = "",
    related_id: str = "",
) -> Optional[InboxMessage]:
    uid = (user_id or "").strip()
    if not uid:
        return None
    if related_type and related_id:
        existing = (
            db.query(InboxMessage)
            .filter(
                InboxMessage.user_id == uid,
                InboxMessage.related_type == related_type,
                InboxMessage.related_id == related_id,
            )
            .first()
        )
        if existing:
            return existing
    msg = InboxMessage(
        user_id=uid,
        title=title,
        body=body,
        level=level,
        link_path=link_path or "",
        related_type=related_type or "",
        related_id=related_id or "",
        is_read=False,
    )
    db.add(msg)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return (
            db.query(InboxMessage)
            .filter(
                InboxMessage.user_id == uid,
                InboxMessage.related_type == related_type,
                InboxMessage.related_id == related_id,
            )
            .first()
        )
    db.refresh(msg)
    return msg


def list_messages(
    db: Session,
    *,
    user_id: str,
    unread_only: bool = False,
    limit: int = 50,
) -> tuple[int, list[InboxMessage]]:
    query = db.query(InboxMessage).filter(InboxMessage.user_id == user_id)
    if unread_only:
        query = query.filter(InboxMessage.is_read == False)  # noqa: E712
    total = query.count()
    items = query.order_by(InboxMessage.created_at.desc()).limit(limit).all()
    return total, items


def unread_count(db: Session, *, user_id: str) -> int:
    return (
        db.query(InboxMessage)
        .filter(InboxMessage.user_id == user_id, InboxMessage.is_read == False)  # noqa: E712
        .count()
    )


def mark_read(db: Session, *, user_id: str, message_id: str) -> Optional[InboxMessage]:
    msg = (
        db.query(InboxMessage)
        .filter(InboxMessage.message_id == message_id, InboxMessage.user_id == user_id)
        .first()
    )
    if not msg:
        return None
    if not msg.is_read:
        msg.is_read = True
        msg.read_at = now_utc()
        db.commit()
        db.refresh(msg)
    return msg


def _task_link_path(task: WorkTask) -> str:
    if task.conv_id:
        return f"/im?conv={task.conv_id}"
    return f"/admin/tasks?task_id={task.task_id}"


def _human_user_ids_from_reporter(reporter: dict) -> list[str]:
    if not reporter or (reporter.get("type") or "").upper() != "HUMAN":
        return []
    uid = (reporter.get("user_id") or "").strip()
    return [uid] if uid else []


def _escalation_user_id(worker: DigitalWorker) -> str:
    contact = worker.escalation_contact or {}
    return (contact.get("user_id") or "").strip()


def notify_work_task(
    db: Session,
    task: WorkTask,
    worker: DigitalWorker,
    *,
    status: TaskStatus,
) -> list[InboxMessage]:
    meta = _TASK_STATUS_NOTIFY.get(status)
    if not meta:
        return []
    title, level = meta
    body = f"{worker.name} · {task.title or task.task_id}"
    link_path = _task_link_path(task)
    related_type = "work_task"
    related_id = f"{task.task_id}:{status.value}"

    recipients: list[str] = []
    for uid in _human_user_ids_from_reporter(task.reporter or {}):
        if uid not in recipients:
            recipients.append(uid)
    if status == TaskStatus.NEED_HUMAN:
        esc_uid = _escalation_user_id(worker)
        if esc_uid and esc_uid not in recipients:
            recipients.append(esc_uid)

    created: list[InboxMessage] = []
    for uid in recipients:
        msg = notify_user(
            db,
            user_id=uid,
            title=title,
            body=body,
            level=level,
            link_path=link_path,
            related_type=related_type,
            related_id=related_id,
        )
        if msg:
            created.append(msg)
    return created


def mark_read_by_task(db: Session, *, user_id: str, task_id: str) -> int:
    uid = (user_id or "").strip()
    tid = (task_id or "").strip()
    if not uid or not tid:
        return 0
    prefix = f"{tid}:"
    msgs = (
        db.query(InboxMessage)
        .filter(
            InboxMessage.user_id == uid,
            InboxMessage.related_type == "work_task",
            InboxMessage.is_read == False,  # noqa: E712
            InboxMessage.related_id.startswith(prefix) | (InboxMessage.related_id == tid),
        )
        .all()
    )
    if not msgs:
        return 0
    stamped = now_utc()
    for msg in msgs:
        msg.is_read = True
        msg.read_at = stamped
    db.commit()
    return len(msgs)
