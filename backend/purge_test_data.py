"""Purge demo / test scenario data from the local worker DB.

Keeps bootstrap org (departments, human users, employee counter) so login still works.
Removes projects, tasks, workers, roles, IM, inbox, and demo-only runtime artifacts.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from models import (
    ProjectActivity, ProjectDocument, ProjectItem, Project,
    WorkTask, TaskEvent, WebhookDelivery,
    Message, ConversationMember, Conversation, WorkerImSession,
    InboxMessage,
    WorkerAuditLog, WorkerSpecHistory, WorkerDutyAgent, WorkerPushRule,
    DigitalWorker, DigitalRole,
)


# Known fixed demo IDs (also covered by full-table wipes below)
DEMO_WORKER_IDS = ("worker-hire", "worker-analyst", "worker-xiaoshen")
DEMO_ROLE_IDS = ("role-hr-recruiter", "role-hr-analyst", "role-audit-assistant")
DEMO_PROJECT_IDS = (
    "proj-campus", "proj-hr-plan", "proj-major",
    "proj-audit-econ", "proj-audit-internal",
)


def purge_test_data(db: Session) -> dict:
    """Delete all demo/test business data. Idempotent."""
    counts: dict[str, int] = {}

    def _wipe(model, label: str):
        n = db.query(model).delete(synchronize_session=False)
        counts[label] = n

    # Order respects FK-ish dependencies (SQLite often has FKs off, still be careful)
    _wipe(ProjectActivity, "project_activities")
    _wipe(ProjectDocument, "project_documents")
    _wipe(ProjectItem, "project_items")
    _wipe(Project, "projects")

    _wipe(WebhookDelivery, "webhook_deliveries")
    _wipe(TaskEvent, "task_events")
    _wipe(WorkTask, "work_tasks")

    _wipe(InboxMessage, "inbox_messages")
    _wipe(Message, "messages")
    _wipe(ConversationMember, "conversation_members")
    _wipe(Conversation, "conversations")
    _wipe(WorkerImSession, "worker_im_sessions")

    _wipe(WorkerAuditLog, "worker_audit_logs")
    _wipe(WorkerSpecHistory, "worker_spec_history")
    _wipe(WorkerDutyAgent, "worker_duty_agents")
    _wipe(WorkerPushRule, "worker_push_rules")
    _wipe(DigitalWorker, "digital_workers")
    _wipe(DigitalRole, "digital_roles")

    db.commit()
    total = sum(counts.values())
    print(f"[purge] removed {total} test/demo rows: {counts}")
    return counts


if __name__ == "__main__":
    from database import SessionLocal, init_db

    init_db()
    session = SessionLocal()
    try:
        purge_test_data(session)
    finally:
        session.close()
