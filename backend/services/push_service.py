"""Proactive push: CRON / EVENT rules via entry COMPOSITE agent."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from models import (
    WorkerPushRule, DigitalWorker, WorkerStatus, Message, MemberType,
    Conversation, gen_uuid, now_utc,
)
from services.vela_agent_client import vela_agent_client, VelaAgentError
from services.im_service import push_message

logger = logging.getLogger(__name__)


def _render_prompt(template: str, worker: DigitalWorker, extra: dict = None) -> str:
    ctx = {
        "worker_name": worker.name,
        "employee_no": worker.employee_no,
        "worker_id": worker.worker_id,
        **(extra or {}),
    }
    text = template or ""
    for k, v in ctx.items():
        text = text.replace("{{" + k + "}}", str(v if v is not None else ""))
    return text


def _cron_due(cron_expr: str, last_run: Optional[datetime], now: datetime) -> bool:
    """Minimal cron: 'M H * * *' (minute hour). Also supports 'every:N' minutes."""
    expr = (cron_expr or "").strip()
    if not expr:
        return False
    if expr.startswith("every:"):
        try:
            mins = int(expr.split(":", 1)[1])
        except ValueError:
            return False
        if mins <= 0:
            return False
        if not last_run:
            return True
        delta = (now - (last_run if last_run.tzinfo else last_run.replace(tzinfo=timezone.utc))).total_seconds()
        return delta >= mins * 60

    parts = expr.split()
    if len(parts) < 2:
        return False
    try:
        minute = int(parts[0]) if parts[0] != "*" else None
        hour = int(parts[1]) if parts[1] != "*" else None
    except ValueError:
        return False

    if minute is not None and now.minute != minute:
        return False
    if hour is not None and now.hour != hour:
        return False
    # once per matching slot
    if last_run:
        lr = last_run if last_run.tzinfo else last_run.replace(tzinfo=timezone.utc)
        if lr.year == now.year and lr.month == now.month and lr.day == now.day and lr.hour == now.hour and (
            minute is None or lr.minute == now.minute
        ):
            return False
    return True


async def _run_entry_chat(worker: DigitalWorker, prompt: str) -> str:
    if not (worker.entry_agent_id or "").strip():
        return f"（{worker.name} 无入口 Agent，跳过推送生成）"
    try:
        sess = vela_agent_client.create_session(
            agent_id=worker.entry_agent_id,
            caller_type="WORKER_PUSH",
            caller_id=worker.worker_id,
        )
        sid = sess["session_id"]
        result = await vela_agent_client.achat(sid, prompt)
        text = ""
        if isinstance(result, dict):
            text = result.get("reply") or result.get("content") or result.get("message") or ""
            if not text and result.get("messages"):
                for m in reversed(result["messages"]):
                    if m.get("role") == "assistant":
                        text = m.get("content", "")
                        break
        if not text:
            sess2 = vela_agent_client.get_session(sid)
            for m in reversed(sess2.get("messages") or []):
                if m.get("role") == "assistant":
                    text = m.get("content", "")
                    break
        try:
            vela_agent_client.close_session(sid)
        except Exception:
            pass
        return text or "（暂无内容）"
    except VelaAgentError as e:
        return f"推送生成失败：{e}"


async def _deliver(db: Session, rule: WorkerPushRule, worker: DigitalWorker, text: str):
    channel = (rule.channel or "IM").upper()
    if channel == "WEBHOOK":
        url = (rule.callback_url or "").strip()
        if not url:
            logger.warning("push rule %s missing callback_url", rule.rule_id)
            return
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                await client.post(url, json={
                    "rule_id": rule.rule_id,
                    "worker_id": worker.worker_id,
                    "worker_name": worker.name,
                    "event_key": rule.event_key,
                    "content": text,
                    "ts": now_utc().isoformat(),
                })
        except Exception as e:
            logger.warning("push webhook failed: %s", e)
        return

    conv_id = (rule.conv_id or "").strip()
    if not conv_id:
        logger.warning("push rule %s missing conv_id", rule.rule_id)
        return
    conv = db.query(Conversation).filter(Conversation.conv_id == conv_id).first()
    if not conv:
        logger.warning("push rule %s conv not found: %s", rule.rule_id, conv_id)
        return
    msg = Message(
        msg_id=gen_uuid(),
        conv_id=conv_id,
        sender_type=MemberType.WORKER,
        sender_id=worker.worker_id,
        msg_type="push",
        content={"text": text, "rule_id": rule.rule_id, "rule_name": rule.name},
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    await push_message(db, msg)


async def execute_rule(db: Session, rule: WorkerPushRule, extra: dict = None) -> dict:
    worker = db.query(DigitalWorker).filter(DigitalWorker.worker_id == rule.worker_id).first()
    if not worker or worker.status != WorkerStatus.ON_DUTY:
        return {"ok": False, "reason": "worker_unavailable"}
    prompt = _render_prompt(rule.prompt_template, worker, extra)
    text = await _run_entry_chat(worker, prompt)
    await _deliver(db, rule, worker, text)
    rule.last_run_at = now_utc()
    rule.updated_at = now_utc()
    db.commit()
    return {"ok": True, "text": text[:500]}


async def trigger_event(db: Session, worker_id: str, event_key: str, extra: dict = None):
    rules = db.query(WorkerPushRule).filter(
        WorkerPushRule.worker_id == worker_id,
        WorkerPushRule.enabled == True,  # noqa: E712
        WorkerPushRule.trigger_type == "EVENT",
        WorkerPushRule.event_key == event_key,
    ).all()
    for rule in rules:
        try:
            await execute_rule(db, rule, extra)
        except Exception as e:
            logger.exception("push event %s rule %s failed: %s", event_key, rule.rule_id, e)


async def process_due_cron_rules(db: Session) -> int:
    now = datetime.now(timezone.utc)
    rules = db.query(WorkerPushRule).filter(
        WorkerPushRule.enabled == True,  # noqa: E712
        WorkerPushRule.trigger_type == "CRON",
    ).all()
    count = 0
    for rule in rules:
        if not _cron_due(rule.cron_expr, rule.last_run_at, now):
            continue
        try:
            await execute_rule(db, rule)
            count += 1
        except Exception as e:
            logger.exception("cron push rule %s failed: %s", rule.rule_id, e)
    return count
