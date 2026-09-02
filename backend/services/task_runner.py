"""Task runner: start agent async chat, poll session, bridge HITL, complete tasks."""
import asyncio
import traceback
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from database import SessionLocal
from config import POLL_INTERVAL_INITIAL, POLL_INTERVAL_MAX, POLL_TIMEOUT_SECONDS
from models import (
    WorkTask, TaskEvent, TaskStatus, DigitalWorker, Message, MemberType,
    Conversation, gen_uuid, now_utc,
)
from services.vela_agent_client import vela_agent_client, VelaAgentError
from services.webhook_dispatcher import enqueue_webhook, build_task_event_payload
from services.im_service import push_message, list_human_member_ids
from services.ws_hub import ws_manager
from services.spec_builder import list_active_worker_duties, get_primary_worker_duty
from services.hitl_bridge import post_approval_card
from services.inbox import notify_work_task
from fastapi import HTTPException


def _add_event(db: Session, task: WorkTask, event: str, detail: dict = None, actor: str = "system"):
    db.add(TaskEvent(task_id=task.task_id, event=event, detail=detail or {}, actor=actor))


def _set_status(db: Session, task: WorkTask, status: TaskStatus, detail: str = ""):
    task.status = status
    task.status_detail = detail
    _add_event(db, task, status.value, {"detail": detail})


async def _notify_task_update(db: Session, task: WorkTask):
    if not task.conv_id:
        return
    users = list_human_member_ids(db, task.conv_id)
    await ws_manager.broadcast_to_users(users, {
        "type": "task_update",
        "data": {
            "task_id": task.task_id,
            "status": task.status.value if hasattr(task.status, "value") else task.status,
            "progress_note": task.progress_note,
        },
    })


def _notify_inbox(db: Session, task: WorkTask, worker: Optional[DigitalWorker], status: TaskStatus):
    w = worker
    if not w:
        w = db.query(DigitalWorker).filter(DigitalWorker.worker_id == task.worker_id).first()
    if w:
        notify_work_task(db, task, w, status=status)


def create_and_start_task(
    db: Session,
    *,
    worker: DigitalWorker,
    source: str,
    title: str,
    instruction: str,
    task_type: str = "",
    context: dict = None,
    priority: str = "NORMAL",
    deadline=None,
    conv_id: Optional[str] = None,
    app_id: Optional[str] = None,
    biz_task_id: str = "",
    callback_url: str = "",
    callback_events: list = None,
    reporter: dict = None,
) -> WorkTask:
    if not (worker.entry_agent_id or "").strip():
        raise HTTPException(status_code=400, detail="数字员工未配置入口 Agent，请先入职编排或修复编排")
    duties = list_active_worker_duties(db, worker.worker_id)
    if not duties:
        raise HTTPException(status_code=400, detail="数字员工未配置职责")

    # optional audit: record matched duty by task_type / text, but always execute via entry agent
    matched = get_primary_worker_duty(db, worker)
    if task_type:
        from services.spec_builder import resolve_duty_for_task_type
        matched = resolve_duty_for_task_type(db, worker, task_type) or matched

    duty_id = matched[1].duty_id if matched else duties[0][1].duty_id
    duty_name = matched[1].name if matched else duties[0][1].name
    duty_gov = (matched[1].governance if matched else {}) or {}

    # concurrency check
    gov = {**duty_gov, **(worker.governance_overrides or {})}
    max_c = gov.get("max_concurrent_tasks", 5)
    running = db.query(WorkTask).filter(
        WorkTask.worker_id == worker.worker_id,
        WorkTask.status.in_([TaskStatus.RUNNING, TaskStatus.NEED_HUMAN, TaskStatus.RECEIVED, TaskStatus.QUEUED]),
    ).count()

    task = WorkTask(
        task_id=gen_uuid(),
        worker_id=worker.worker_id,
        duty_id=duty_id,
        source=source,
        task_type=task_type or "",
        title=title,
        instruction=instruction,
        context=context or {},
        priority=priority,
        deadline=deadline,
        conv_id=conv_id,
        app_id=app_id,
        biz_task_id=biz_task_id or "",
        callback_url=callback_url or "",
        callback_events=callback_events or ["ACCEPTED", "NEED_HUMAN", "COMPLETED", "FAILED"],
        reporter=reporter or {},
        status=TaskStatus.QUEUED if running >= max_c else TaskStatus.RECEIVED,
    )
    db.add(task)
    db.flush()
    _add_event(db, task, task.status.value, {
        "title": title,
        "duty_id": duty_id,
        "duty_name": duty_name,
        "entry_agent_id": worker.entry_agent_id,
    })
    db.commit()
    db.refresh(task)

    enqueue_webhook(db, task, "ACCEPTED", build_task_event_payload(task, "ACCEPTED"))
    return task


def start_queued_tasks(db: Session):
    """Promote queued tasks when capacity frees."""
    queued = db.query(WorkTask).filter(WorkTask.status == TaskStatus.QUEUED).order_by(WorkTask.created_at).all()
    for task in queued:
        worker = db.query(DigitalWorker).filter(DigitalWorker.worker_id == task.worker_id).first()
        if not worker:
            continue
        max_c = (worker.governance_overrides or {}).get("max_concurrent_tasks", 5)
        running = db.query(WorkTask).filter(
            WorkTask.worker_id == worker.worker_id,
            WorkTask.status.in_([TaskStatus.RUNNING, TaskStatus.NEED_HUMAN, TaskStatus.RECEIVED]),
        ).count()
        if running < max_c:
            task.status = TaskStatus.RECEIVED
            db.commit()
            schedule_task(task.task_id)


async def run_task(task_id: str):
    db = SessionLocal()
    try:
        task = db.query(WorkTask).filter(WorkTask.task_id == task_id).first()
        if not task:
            return
        worker = db.query(DigitalWorker).filter(DigitalWorker.worker_id == task.worker_id).first()
        agent_id = (worker.entry_agent_id or "").strip() if worker else ""
        token_budget = 100000
        if worker:
            gov = dict(worker.governance_overrides or {})
            if task.duty_id:
                from models import Duty
                duty = db.query(Duty).filter(Duty.duty_id == task.duty_id).first()
                if duty:
                    gov = {**(duty.governance or {}), **gov}
            token_budget = gov.get("token_budget_per_task", gov.get("token_budget", 100000))

        if not worker or not agent_id:
            _set_status(db, task, TaskStatus.FAILED, "数字员工未配置入口 Agent")
            db.commit()
            _notify_inbox(db, task, worker, TaskStatus.FAILED)
            return

        # create agent session on entry COMPOSITE
        try:
            sess = vela_agent_client.create_session(
                agent_id=agent_id,
                caller_type="WORKER_TASK",
                caller_id=task.task_id,
                token_budget=token_budget,
            )
            session_id = sess["session_id"]
        except VelaAgentError as e:
            _set_status(db, task, TaskStatus.FAILED, f"创建会话失败: {e}")
            db.commit()
            _notify_inbox(db, task, worker, TaskStatus.FAILED)
            enqueue_webhook(db, task, "FAILED", build_task_event_payload(task, "FAILED"))
            await _post_result_card(db, task, success=False)
            return

        task.agent_session_id = session_id
        task.started_at = now_utc()
        _set_status(db, task, TaskStatus.RUNNING)
        db.commit()

        # IM task_card update
        await _upsert_task_card(db, task)

        message = f"【任务】{task.title}\n\n{task.instruction}"
        if task.task_type:
            message = f"【任务类型】{task.task_type}\n" + message
        if task.context:
            message += f"\n\n【上下文】\n{task.context}"

        try:
            await vela_agent_client.achat_async(session_id, message)
        except VelaAgentError as e:
            _set_status(db, task, TaskStatus.FAILED, f"提交执行失败: {e}")
            db.commit()
            _notify_inbox(db, task, worker, TaskStatus.FAILED)
            enqueue_webhook(db, task, "FAILED", build_task_event_payload(task, "FAILED"))
            await _post_result_card(db, task, success=False)
            return

        # poll loop
        interval = POLL_INTERVAL_INITIAL
        elapsed = 0.0
        hitl_notified = set()

        while elapsed < POLL_TIMEOUT_SECONDS:
            await asyncio.sleep(interval)
            elapsed += interval
            interval = min(interval * 1.3, POLL_INTERVAL_MAX)

            db.refresh(task)
            if task.status == TaskStatus.CANCELED:
                return

            try:
                sess = await vela_agent_client.aget_session(session_id)
            except VelaAgentError:
                continue

            status = sess.get("status", "")
            messages = sess.get("messages") or []
            task.tokens_used = sess.get("token_used") or task.tokens_used or 0

            # progress from last assistant/tool
            for m in reversed(messages):
                if m.get("role") in ("assistant", "tool") and m.get("content"):
                    note = str(m["content"])[:200]
                    if note != task.progress_note:
                        task.progress_note = note
                        db.commit()
                        await _notify_task_update(db, task)
                    break

            if status == "HITL_WAIT":
                if task.status != TaskStatus.NEED_HUMAN:
                    _set_status(db, task, TaskStatus.NEED_HUMAN, "等待人工审批/确认")
                    db.commit()
                    _notify_inbox(db, task, worker, TaskStatus.NEED_HUMAN)
                    enqueue_webhook(
                        db, task, "NEED_HUMAN",
                        build_task_event_payload(task, "NEED_HUMAN", {
                            "need_human": {"reason": "tool_approval"},
                        }),
                    )
                    await _notify_task_update(db, task)
                    try:
                        from services.push_service import trigger_event
                        await trigger_event(db, task.worker_id, "NEED_HUMAN", {
                            "task_id": task.task_id,
                            "title": task.title,
                            "status": "NEED_HUMAN",
                        })
                    except Exception:
                        pass
                # bridge approvals
                try:
                    approvals = await vela_agent_client.alist_pending_approvals(session_id)
                except VelaAgentError:
                    approvals = []
                for ap in approvals:
                    aid = ap.get("approval_id")
                    if aid and aid not in hitl_notified:
                        hitl_notified.add(aid)
                        await post_approval_card(
                            db,
                            conv_id=task.conv_id,
                            worker=worker,
                            task_id=task.task_id,
                            session_id=session_id,
                            approval=ap,
                        )
                continue

            if status == "RUNNING":
                if task.status == TaskStatus.NEED_HUMAN:
                    _set_status(db, task, TaskStatus.RUNNING, "已恢复执行")
                    db.commit()
                    await _notify_task_update(db, task)
                continue

            if status == "ERROR":
                _set_status(db, task, TaskStatus.FAILED, "Agent 会话错误")
                task.finished_at = now_utc()
                db.commit()
                _notify_inbox(db, task, worker, TaskStatus.FAILED)
                enqueue_webhook(db, task, "FAILED", build_task_event_payload(task, "FAILED"))
                await _post_result_card(db, task, success=False)
                try:
                    vela_agent_client.close_session(session_id)
                except Exception:
                    pass
                start_queued_tasks(db)
                return

            if status in ("ACTIVE", "IDLE", "CLOSED"):
                # completed
                summary = ""
                for m in reversed(messages):
                    if m.get("role") == "assistant":
                        summary = m.get("content", "")
                        break
                task.result = {"summary": summary}
                task.finished_at = now_utc()
                _set_status(db, task, TaskStatus.COMPLETED, "完成")
                db.commit()
                _notify_inbox(db, task, worker, TaskStatus.COMPLETED)
                enqueue_webhook(db, task, "COMPLETED", build_task_event_payload(task, "COMPLETED"))
                await _post_result_card(db, task, success=True)
                try:
                    from services.push_service import trigger_event
                    await trigger_event(db, task.worker_id, "TASK_COMPLETED", {
                        "task_id": task.task_id,
                        "title": task.title,
                        "summary": (task.result or {}).get("summary", "")[:800],
                        "status": "COMPLETED",
                    })
                except Exception:
                    pass
                try:
                    vela_agent_client.close_session(session_id)
                except Exception:
                    pass
                start_queued_tasks(db)
                return

        # timeout
        _set_status(db, task, TaskStatus.FAILED, "执行超时")
        task.finished_at = now_utc()
        db.commit()
        _notify_inbox(db, task, worker, TaskStatus.FAILED)
        try:
            vela_agent_client.abort_session(session_id)
        except Exception:
            pass
        enqueue_webhook(db, task, "FAILED", build_task_event_payload(task, "FAILED"))
        await _post_result_card(db, task, success=False)
        start_queued_tasks(db)

    except Exception as e:
        traceback.print_exc()
        try:
            task = db.query(WorkTask).filter(WorkTask.task_id == task_id).first()
            if task and task.status not in (TaskStatus.COMPLETED, TaskStatus.CANCELED, TaskStatus.FAILED):
                _set_status(db, task, TaskStatus.FAILED, str(e))
                task.finished_at = now_utc()
                db.commit()
                worker = db.query(DigitalWorker).filter(DigitalWorker.worker_id == task.worker_id).first()
                _notify_inbox(db, task, worker, TaskStatus.FAILED)
        except Exception:
            pass
    finally:
        db.close()


async def _upsert_task_card(db: Session, task: WorkTask):
    if not task.conv_id:
        return
    worker = db.query(DigitalWorker).filter(DigitalWorker.worker_id == task.worker_id).first()
    content = {
        "task_id": task.task_id,
        "title": task.title,
        "status": task.status.value if hasattr(task.status, "value") else task.status,
        "instruction": task.instruction[:300],
        "worker_name": worker.name if worker else "",
    }
    # check existing task_card
    existing = db.query(Message).filter(
        Message.conv_id == task.conv_id,
        Message.ref_task_id == task.task_id,
        Message.msg_type == "task_card",
    ).first()
    if existing:
        existing.content = content
        db.commit()
        await push_message(db, existing)
    else:
        msg = Message(
            msg_id=gen_uuid(),
            conv_id=task.conv_id,
            sender_type=MemberType.WORKER,
            sender_id=task.worker_id,
            msg_type="task_card",
            content=content,
            ref_task_id=task.task_id,
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)
        await push_message(db, msg)


async def _post_result_card(db: Session, task: WorkTask, success: bool):
    await _upsert_task_card(db, task)
    if not task.conv_id:
        return
    summary = (task.result or {}).get("summary", task.status_detail or "")
    msg = Message(
        msg_id=gen_uuid(),
        conv_id=task.conv_id,
        sender_type=MemberType.WORKER,
        sender_id=task.worker_id,
        msg_type="result_card",
        content={
            "task_id": task.task_id,
            "title": task.title,
            "success": success,
            "status": task.status.value if hasattr(task.status, "value") else task.status,
            "summary": summary,
        },
        ref_task_id=task.task_id,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    await push_message(db, msg)
    await _notify_task_update(db, task)


def cancel_task(db: Session, task_id: str, actor: str = "system") -> WorkTask:
    task = db.query(WorkTask).filter(WorkTask.task_id == task_id).first()
    if not task:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELED):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"任务已结束: {task.status}")
    if task.agent_session_id:
        try:
            vela_agent_client.abort_session(task.agent_session_id)
        except Exception:
            pass
    _set_status(db, task, TaskStatus.CANCELED, f"由 {actor} 取消")
    task.finished_at = now_utc()
    db.commit()
    db.refresh(task)
    start_queued_tasks(db)
    return task


def schedule_task(task_id: str):
    """Schedule run_task safely from sync context. Skips QUEUED tasks."""
    db = SessionLocal()
    try:
        task = db.query(WorkTask).filter(WorkTask.task_id == task_id).first()
        if not task or task.status == TaskStatus.QUEUED:
            return
        if task.status not in (TaskStatus.RECEIVED, TaskStatus.RUNNING):
            # allow re-entry only for RECEIVED
            if task.status != TaskStatus.RECEIVED:
                pass
    finally:
        db.close()

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(run_task(task_id))
        else:
            asyncio.run(run_task(task_id))
    except RuntimeError:
        import threading

        def _run():
            asyncio.run(run_task(task_id))

        threading.Thread(target=_run, daemon=True).start()
