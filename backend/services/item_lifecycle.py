"""Helpers for pausing / resuming item progress_steps."""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from models import ProjectItem, WorkTask, TaskStatus, now_utc


PAUSED_STEP_STATUSES = ("running",)
RESUME_RESET_STATUSES = ("suspended", "cancelled", "canceled", "running", "failed")


def normalize_steps_on_pause(steps: Optional[list], actor: str = "system") -> List[dict]:
    """Mark in-flight steps as suspended (已暂停), never leave them as running."""
    out = []
    for s in list(steps or []):
        step = dict(s)
        if step.get("status") in PAUSED_STEP_STATUSES:
            step["status"] = "suspended"
            detail = step.get("detail")
            suffix = f"（已暂停，by {actor}）"
            if detail is None or detail == "":
                step["detail"] = f"已暂停（by {actor}）"
            else:
                step["detail"] = f"{detail}{suffix}"
            step["finished_at"] = now_utc().isoformat()
        out.append(step)
    return out


def normalize_steps_on_resume(steps: Optional[list]) -> List[dict]:
    """Reset paused/failed mid-steps to pending so execution can continue."""
    out = []
    for s in list(steps or []):
        step = dict(s)
        if step.get("status") in RESUME_RESET_STATUSES:
            step["status"] = "pending"
            # keep detail for audit but trim pause markers for clarity
            step["started_at"] = ""
            step["finished_at"] = ""
        out.append(step)
    return out


def apply_pause_to_item_and_task(
    db: Session,
    item: ProjectItem,
    *,
    actor: str = "system",
) -> Optional[WorkTask]:
    """
    Always rewrite running → suspended on item meta and linked task.
    Cancel active task when still running/queued/etc.
    """
    from services.task_runner import cancel_task

    task = None
    if item.task_id:
        task = db.query(WorkTask).filter(WorkTask.task_id == item.task_id).first()

    if task and task.status not in (
        TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELED,
    ):
        cancel_task(db, item.task_id, actor=actor)
        db.refresh(task)

    # Re-load steps after cancel (cancel may have set cancelled); unify to suspended for pause UX
    steps_src = None
    if task:
        db.refresh(task)
        steps_src = list(task.progress_steps or [])
    if not steps_src:
        steps_src = list((item.meta or {}).get("progress_steps") or [])

    paused = []
    for s in steps_src:
        step = dict(s)
        if step.get("status") in ("running", "cancelled", "canceled"):
            step["status"] = "suspended"
            detail = step.get("detail")
            if not detail:
                step["detail"] = f"已暂停（by {actor}）"
            elif "已暂停" not in str(detail):
                step["detail"] = f"{detail}（已暂停，by {actor}）"
            step.setdefault("finished_at", now_utc().isoformat())
        paused.append(step)

    if task:
        task.progress_steps = paused
        task.progress_note = "事项已暂停"
    meta = dict(item.meta or {})
    meta["progress_steps"] = paused
    meta["progress_note"] = "事项已暂停"
    item.meta = meta
    db.flush()
    return task
