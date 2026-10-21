"""BPM project-item task orchestration: plan → execute steps → finalize report."""
from __future__ import annotations

import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from auth_config import PROJECT_DOCS_DIR
from database import SessionLocal
from models import (
    DigitalWorker,
    Project,
    ProjectDocSource,
    ProjectItem,
    ProjectOwnerType,
    TaskSource,
    TaskStatus,
    WorkTask,
    gen_uuid,
    now_utc,
)
from services.orchestration_schema import (
    build_fallback_plan,
    build_planning_prompt,
    materialize_progress_steps,
    parse_work_plan,
)
from services.project_service import (
    append_project_activity,
    create_project_document,
    sync_item_from_task,
)
from services.spec_builder import list_active_worker_duties, resolve_duty_for_task_type, get_primary_worker_duty
from services.vela_agent_client import VelaAgentError, vela_agent_client
from services.webhook_dispatcher import build_task_event_payload, enqueue_webhook


def scope_duties_for_task(
    db: Session,
    worker: DigitalWorker,
    task: WorkTask,
    duties: List[Tuple],
) -> List[Tuple]:
    """Limit orchestration to the duty matched by this item/task, not all worker duties."""
    if not duties:
        return duties
    matched = None
    duty_id = getattr(task, "duty_id", None) or ""
    task_type = getattr(task, "task_type", None) or ""
    if duty_id:
        for pair in duties:
            if pair[1].duty_id == duty_id:
                matched = pair
                break
    if matched is None and str(task_type).strip():
        matched = resolve_duty_for_task_type(db, worker, task_type)
    if matched is None:
        matched = get_primary_worker_duty(db, worker) or duties[0]
    return [matched]


def _filter_plan_to_scoped_duties(plan: dict, scoped: List[Tuple], item_name: str = "") -> dict:
    allowed = {d.duty_id for _, d in scoped}
    primary_id = scoped[0][1].duty_id if scoped else ""
    steps = []
    for s in plan.get("steps") or []:
        did = (s.get("duty_id") or "").strip()
        if did and did not in allowed:
            # drop cross-item / other-duty collab steps from LLM
            continue
        if not did:
            s = {**s, "duty_id": primary_id}
        steps.append(s)
    if len(steps) < 2:
        return build_fallback_plan(scoped, item_name)
    return {**plan, "steps": steps}


def _token_budget(db: Session, worker: DigitalWorker, duty_id: Optional[str] = None) -> int:
    gov = dict(worker.governance_overrides or {})
    if duty_id:
        from models import Duty
        duty = db.query(Duty).filter(Duty.duty_id == duty_id).first()
        if duty:
            gov = {**(duty.governance or {}), **gov}
    return gov.get("token_budget_per_task", gov.get("token_budget", 100000))


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _sync_and_notify(db: Session, task: WorkTask):
    from services.task_runner import _notify_task_update

    sync_item_from_task(db, task)
    await _notify_task_update(db, task)


def _save_steps(task: WorkTask, steps: list):
    task.progress_steps = steps


async def plan_item_work(
    db: Session,
    task: WorkTask,
    item: ProjectItem,
    worker: DigitalWorker,
    duties: List[Tuple],
) -> str:
    """
    Ask entry agent for a structured plan (or fallback), write progress_steps.
    Returns intent string.
    """
    from services.task_runner import _add_event, _set_status

    entry_id = (worker.entry_agent_id or "").strip()
    ctx = task.context or {}
    project_name = ctx.get("project_name") or ""
    if not project_name and item.project_id:
        proj = db.query(Project).filter(Project.project_id == item.project_id).first()
        project_name = proj.name if proj else ""

    prompt = build_planning_prompt(
        item_name=item.name,
        item_description=item.description or ctx.get("item_description") or "",
        instruction=task.instruction or "",
        planned_start=item.planned_start or ctx.get("planned_start"),
        planned_end=item.planned_end or ctx.get("planned_end"),
        project_name=project_name,
        duties=duties,
    )

    plan = None
    plan_text = ""
    if entry_id:
        try:
            sess = vela_agent_client.create_session(
                agent_id=entry_id,
                caller_type="WORKER_PLAN",
                caller_id=task.task_id,
                token_budget=_token_budget(db, worker, task.duty_id),
            )
            session_id = sess["session_id"]
            task.agent_session_id = session_id
            db.commit()
            await vela_agent_client.achat_async(session_id, prompt)
            from services.task_runner import poll_session_until_done

            outcome = await poll_session_until_done(
                db, task, worker, session_id,
                update_ad_hoc_progress=False,
                close_on_done=True,
            )
            plan_text = outcome.get("summary") or ""
            if outcome.get("ok"):
                plan = parse_work_plan(plan_text)
            # if HITL/failed during plan, still try parse; else fallback
        except Exception:
            traceback.print_exc()
            plan = None

    if not plan:
        plan = build_fallback_plan(duties, item.name)
        _add_event(db, task, "PLAN_FALLBACK", {"reason": "parse_or_agent_failed"})
    else:
        plan = _filter_plan_to_scoped_duties(plan, duties, item.name)
        if not plan.get("intent"):
            plan["intent"] = f"完成事项「{item.name}」并提交工作报告"

    intent, steps = materialize_progress_steps(
        plan,
        duties,
        entry_id,
        planned_start=item.planned_start or ctx.get("planned_start"),
        planned_end=item.planned_end or ctx.get("planned_end"),
    )
    _save_steps(task, steps)
    task.progress_note = intent
    task.progress_pct = 5
    task.result = {**(task.result or {}), "intent": intent}
    _set_status(db, task, TaskStatus.RUNNING, "已完成工作规划")
    _add_event(db, task, "PLANNED", {"intent": intent, "steps": len(steps)})
    db.commit()
    await _sync_and_notify(db, task)
    return intent


async def execute_planned_steps(
    db: Session,
    task: WorkTask,
    item: ProjectItem,
    worker: DigitalWorker,
) -> bool:
    """
    Run each progress step sequentially via its agent_id.
    Returns False if a step failed fatally.
    """
    from services.task_runner import (
        _add_event,
        _set_status,
        poll_session_until_done,
        start_queued_tasks,
    )

    steps = list(task.progress_steps or [])
    if not steps:
        return False

    prior_summaries: List[str] = []
    total = len(steps)

    for idx, step in enumerate(steps):
        db.refresh(task)
        if task.status == TaskStatus.CANCELED:
            return False

        steps = list(task.progress_steps or [])
        step = steps[idx]
        # Resume: skip already completed steps
        if step.get("status") == "completed":
            prior_summaries.append(
                f"{step.get('title')}: {step.get('result') or step.get('detail') or '已完成'}"
            )
            continue
        agent_id = (step.get("agent_id") or worker.entry_agent_id or "").strip()
        if not agent_id:
            step["status"] = "failed"
            step["detail"] = "未配置执行 Agent"
            step["finished_at"] = _iso_now()
            _save_steps(task, steps)
            _set_status(db, task, TaskStatus.FAILED, f"步骤失败: {step.get('title')}")
            db.commit()
            await _sync_and_notify(db, task)
            return False

        step["status"] = "running"
        step["started_at"] = _iso_now()
        step["detail"] = "正在执行…"
        _save_steps(task, steps)
        task.progress_note = f"执行中: {step.get('title')}"
        task.progress_pct = max(5, int((idx / total) * 90))
        _set_status(db, task, TaskStatus.RUNNING, f"执行步骤 {idx + 1}/{total}")
        db.commit()
        await _sync_and_notify(db, task)

        prior_block = "\n".join(f"- {s}" for s in prior_summaries[-5:]) or "(无)"
        message = (
            f"【事项】{item.name}\n"
            f"【步骤】{step.get('title')}\n"
            f"【本步目标】{step.get('intent') or step.get('title')}\n"
            f"【委派说明】{task.instruction or '-'}\n"
            f"【前序摘要】\n{prior_block}\n\n"
            "请完成本步骤工作，并在回复中给出：结果摘要；如有产出文件请列出文件名。"
        )

        try:
            sess = vela_agent_client.create_session(
                agent_id=agent_id,
                caller_type="WORKER_STEP",
                caller_id=f"{task.task_id}:{step.get('key')}",
                token_budget=_token_budget(db, worker, step.get("duty_id")),
            )
            session_id = sess["session_id"]
            task.agent_session_id = session_id
            db.commit()
            await vela_agent_client.achat_async(session_id, message)
        except VelaAgentError as e:
            step["status"] = "failed"
            step["detail"] = str(e)
            step["finished_at"] = _iso_now()
            _save_steps(task, steps)
            _set_status(db, task, TaskStatus.FAILED, f"步骤提交失败: {e}")
            db.commit()
            await _sync_and_notify(db, task)
            return False

        outcome = await poll_session_until_done(
            db,
            task,
            worker,
            session_id,
            update_ad_hoc_progress=False,
            close_on_done=True,
            on_progress=lambda note, _step=step, _steps=steps, _task=task: _touch_step_detail(
                _task, _steps, _step, note
            ),
        )

        steps = list(task.progress_steps or [])
        step = steps[idx]
        summary = (outcome.get("summary") or "").strip()
        if outcome.get("canceled"):
            if step.get("status") == "running":
                step["status"] = "cancelled"
                step["detail"] = (step.get("detail") or "已暂停")[:300]
                step["finished_at"] = _iso_now()
                _save_steps(task, steps)
                db.commit()
                await _sync_and_notify(db, task)
            return False
        if not outcome.get("ok"):
            step["status"] = "failed"
            step["detail"] = outcome.get("error") or "步骤执行失败"
            step["result"] = summary[:500]
            step["finished_at"] = _iso_now()
            _save_steps(task, steps)
            _set_status(db, task, TaskStatus.FAILED, f"步骤失败: {step.get('title')}")
            db.commit()
            await _sync_and_notify(db, task)
            return False

        step["status"] = "completed"
        step["detail"] = summary[:300] if summary else "已完成"
        step["result"] = summary[:800] if summary else "完成"
        step["finished_at"] = _iso_now()
        # lightweight output filenames from text
        outputs = _extract_output_names(summary)
        if outputs:
            step["outputs"] = [{"name": n} for n in outputs]
        _save_steps(task, steps)
        completed = idx + 1
        task.progress_pct = min(90, int((completed / total) * 90))
        task.progress_note = f"已完成: {step.get('title')}"
        _add_event(db, task, "STEP_DONE", {"key": step.get("key"), "title": step.get("title")})
        db.commit()
        await _sync_and_notify(db, task)
        prior_summaries.append(f"{step.get('title')}: {summary[:200]}")

    return True


def _touch_step_detail(task: WorkTask, steps: list, step: dict, note: str):
    key = step.get("key")
    text = "" if note is None else str(note)
    for s in steps:
        if s.get("key") == key and s.get("status") == "running":
            s["detail"] = text[:300]
            break
    task.progress_steps = steps
    task.progress_note = text[:200] if text else task.progress_note


def _extract_output_names(text: str) -> List[str]:
    if not text:
        return []
    import re
    names = re.findall(
        r"[\w\u4e00-\u9fff\-]+\.(?:xlsx?|docx?|pdf|md|txt|csv|png|jpg)",
        text,
        flags=re.IGNORECASE,
    )
    # dedupe preserve order
    seen = set()
    out = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out[:8]


async def finalize_report(
    db: Session,
    task: WorkTask,
    item: ProjectItem,
    worker: DigitalWorker,
    intent: str,
) -> None:
    """Aggregate step results into report, artifacts, and project documents."""
    from services.task_runner import (
        _add_event,
        _notify_inbox,
        _post_result_card,
        _set_status,
        start_queued_tasks,
    )

    steps = list(task.progress_steps or [])
    steps_summary_lines = []
    for s in steps:
        steps_summary_lines.append(
            f"- [{s.get('status')}] {s.get('title')}: {s.get('result') or s.get('detail') or '-'}"
        )
    steps_block = "\n".join(steps_summary_lines) or "(无步骤)"

    report = ""
    entry_id = (worker.entry_agent_id or "").strip()
    report_prompt = (
        "请根据以下事项与步骤结果，撰写一份简洁的工作报告（Markdown）。\n"
        "包含：工作意图、完成情况、关键结果、产出资料清单、风险/待跟进。\n"
        f"【事项】{item.name}\n"
        f"【意图】{intent}\n"
        f"【步骤结果】\n{steps_block}\n"
    )
    if entry_id:
        try:
            sess = vela_agent_client.create_session(
                agent_id=entry_id,
                caller_type="WORKER_REPORT",
                caller_id=task.task_id,
                token_budget=_token_budget(db, worker, task.duty_id),
            )
            session_id = sess["session_id"]
            await vela_agent_client.achat_async(session_id, report_prompt)
            from services.task_runner import poll_session_until_done

            outcome = await poll_session_until_done(
                db, task, worker, session_id,
                update_ad_hoc_progress=False,
                close_on_done=True,
            )
            if outcome.get("ok"):
                report = (outcome.get("summary") or "").strip()
        except Exception:
            traceback.print_exc()

    if not report:
        report = (
            f"# 工作报告：{item.name}\n\n"
            f"## 工作意图\n{intent}\n\n"
            f"## 步骤完成情况\n{steps_block}\n\n"
            f"## 结论\n事项「{item.name}」相关步骤已执行完毕。\n"
        )

    # collect artifacts from steps + report file
    artifacts = []
    for s in steps:
        for o in s.get("outputs") or []:
            if isinstance(o, dict) and o.get("name"):
                artifacts.append({"name": o["name"], "step_key": s.get("key"), "source": "step"})
            elif isinstance(o, str):
                artifacts.append({"name": o, "step_key": s.get("key"), "source": "step"})

    project = db.query(Project).filter(Project.project_id == item.project_id).first()
    report_name = f"{item.name}-工作报告.md"
    doc_meta = None
    if project:
        PROJECT_DOCS_DIR.mkdir(parents=True, exist_ok=True)
        stored = f"{gen_uuid().replace('-', '')[:16]}_report.md"
        dest = PROJECT_DOCS_DIR / stored
        content = report.encode("utf-8")
        dest.write_bytes(content)
        doc_meta = create_project_document(
            db,
            project,
            name=report_name,
            file_path=f"/project-docs/{stored}",
            mime_type="text/markdown",
            size_bytes=len(content),
            owner_id=worker.worker_id,
            owner_name=worker.name or "",
            source=ProjectDocSource.AI_GENERATED,
            owner_type=ProjectOwnerType.WORKER,
        )
        artifacts.insert(0, {
            "name": report_name,
            "doc_id": doc_meta.get("doc_id"),
            "path": doc_meta.get("file_path"),
            "mime_type": "text/markdown",
            "source": "report",
        })
        # placeholder docs for named outputs without files
        for art in list(artifacts):
            if art.get("doc_id") or art.get("source") == "report":
                continue
            name = art.get("name") or "产出.txt"
            stub = f"# {name}\n\n由数字员工「{worker.name}」在事项「{item.name}」中产出。\n"
            stored2 = f"{gen_uuid().replace('-', '')[:16]}_{Path(name).stem}.md"
            dest2 = PROJECT_DOCS_DIR / stored2
            data2 = stub.encode("utf-8")
            dest2.write_bytes(data2)
            d2 = create_project_document(
                db,
                project,
                name=name if name.endswith((".md", ".txt")) else f"{name}.md",
                file_path=f"/project-docs/{stored2}",
                mime_type="text/markdown",
                size_bytes=len(data2),
                owner_id=worker.worker_id,
                owner_name=worker.name or "",
                source=ProjectDocSource.AI_GENERATED,
                owner_type=ProjectOwnerType.WORKER,
            )
            art["doc_id"] = d2.get("doc_id")
            art["path"] = d2.get("file_path")
            art["mime_type"] = "text/markdown"

        append_project_activity(
            db,
            item.project_id,
            f"{worker.name}提交「{item.name}」工作报告",
            kind="report",
            actor_type=ProjectOwnerType.WORKER,
            actor_id=worker.worker_id,
            actor_name=worker.name or "",
            commit=False,
        )

    task.result = {
        "summary": report[:2000],
        "intent": intent,
        "report": report,
        "steps_summary": steps_summary_lines,
    }
    task.artifacts = artifacts
    task.progress_pct = 100
    task.progress_note = "已提交工作报告"
    task.finished_at = now_utc()
    # mark any leftover pending as completed skip? leave as-is
    _set_status(db, task, TaskStatus.COMPLETED, "完成")
    _add_event(db, task, "REPORT_SUBMITTED", {"artifacts": len(artifacts)})
    db.commit()
    await _sync_and_notify(db, task)
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
    start_queued_tasks(db)


async def run_orchestrated_task(task_id: str):
    """Full pipeline for BPM + item_id tasks."""
    from services.task_runner import (
        _notify_inbox,
        _post_result_card,
        _set_status,
        _upsert_task_card,
        start_queued_tasks,
    )

    db = SessionLocal()
    try:
        task = db.query(WorkTask).filter(WorkTask.task_id == task_id).first()
        if not task:
            return
        worker = db.query(DigitalWorker).filter(DigitalWorker.worker_id == task.worker_id).first()
        item = db.query(ProjectItem).filter(ProjectItem.item_id == task.item_id).first() if task.item_id else None
        if not worker or not (worker.entry_agent_id or "").strip():
            _set_status(db, task, TaskStatus.FAILED, "数字员工未配置入口 Agent")
            db.commit()
            _notify_inbox(db, task, worker, TaskStatus.FAILED)
            return
        if not item:
            _set_status(db, task, TaskStatus.FAILED, "关联事项不存在")
            db.commit()
            _notify_inbox(db, task, worker, TaskStatus.FAILED)
            return

        duties = list_active_worker_duties(db, worker.worker_id)
        scoped = scope_duties_for_task(db, worker, task, duties)
        task.started_at = now_utc()
        _set_status(db, task, TaskStatus.RUNNING, "开始编排")
        db.commit()
        await _upsert_task_card(db, task)
        await _sync_and_notify(db, task)

        existing_steps = list(task.progress_steps or [])
        ctx = task.context if isinstance(task.context, dict) else {}
        resume_mode = bool(ctx.get("resume")) or any(
            s.get("status") == "completed" for s in existing_steps
        )
        if resume_mode and existing_steps:
            intent = (task.result or {}).get("intent") or task.progress_note or "继续执行"
        else:
            intent = await plan_item_work(db, task, item, worker, scoped)
        db.refresh(task)
        if task.status == TaskStatus.CANCELED:
            return

        ok = await execute_planned_steps(db, task, item, worker)
        db.refresh(task)
        if task.status == TaskStatus.CANCELED:
            return
        if not ok:
            enqueue_webhook(db, task, "FAILED", build_task_event_payload(task, "FAILED"))
            await _post_result_card(db, task, success=False)
            _notify_inbox(db, task, worker, TaskStatus.FAILED)
            start_queued_tasks(db)
            return

        await finalize_report(db, task, item, worker, intent)

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
                await _post_result_card(db, task, success=False)
                start_queued_tasks(db)
        except Exception:
            pass
    finally:
        db.close()


def should_orchestrate(task: WorkTask) -> bool:
    if not task.item_id:
        return False
    src = task.source.value if hasattr(task.source, "value") else task.source
    return src == TaskSource.BPM.value or src == "BPM"
