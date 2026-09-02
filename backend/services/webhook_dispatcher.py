"""Webhook delivery with HMAC signature and retry."""
import hashlib
import hmac
import json
from datetime import timedelta
from typing import Optional
import httpx
from sqlalchemy.orm import Session
from config import WEBHOOK_RETRY_DELAYS_MIN
from models import WebhookDelivery, WorkTask, OpenApp, gen_uuid, now_utc


def sign_payload(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def enqueue_webhook(db: Session, task: WorkTask, event: str, payload: dict):
    if not task.callback_url:
        return None
    events = task.callback_events or []
    if events and event not in events:
        return None
    delivery = WebhookDelivery(
        delivery_id=gen_uuid(),
        task_id=task.task_id,
        event=event,
        payload=payload,
        url=task.callback_url,
        status="PENDING",
        attempts=0,
        next_retry_at=now_utc(),
    )
    db.add(delivery)
    db.commit()
    db.refresh(delivery)
    return delivery


def _app_secret_for_task(db: Session, task: WorkTask) -> str:
    if not task.app_id:
        return "vela-worker-default-secret"
    app = db.query(OpenApp).filter(OpenApp.app_id == task.app_id).first()
    return app.app_secret if app else "vela-worker-default-secret"


def deliver_once(db: Session, delivery: WebhookDelivery) -> bool:
    task = db.query(WorkTask).filter(WorkTask.task_id == delivery.task_id).first()
    secret = _app_secret_for_task(db, task) if task else "vela-worker-default-secret"
    body_obj = {
        **(delivery.payload or {}),
        "event": delivery.event,
        "delivery_id": delivery.delivery_id,
        "occurred_at": now_utc().isoformat(),
    }
    body = json.dumps(body_obj, ensure_ascii=False, default=str).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-Vela-Signature": sign_payload(secret, body),
        "X-Vela-Event": delivery.event,
    }
    delivery.attempts = (delivery.attempts or 0) + 1
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(delivery.url, content=body, headers=headers)
        if 200 <= resp.status_code < 300:
            delivery.status = "SUCCESS"
            delivery.last_error = ""
            db.commit()
            return True
        delivery.last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        delivery.last_error = str(e)

    # schedule retry
    idx = delivery.attempts - 1
    if idx < len(WEBHOOK_RETRY_DELAYS_MIN):
        delivery.status = "PENDING"
        delivery.next_retry_at = now_utc() + timedelta(minutes=WEBHOOK_RETRY_DELAYS_MIN[idx])
    else:
        delivery.status = "FAILED"
    db.commit()
    return False


def process_pending_webhooks(db: Session, limit: int = 20):
    now = now_utc()
    rows = (
        db.query(WebhookDelivery)
        .filter(WebhookDelivery.status == "PENDING")
        .filter(
            (WebhookDelivery.next_retry_at == None) | (WebhookDelivery.next_retry_at <= now)  # noqa: E711
        )
        .limit(limit)
        .all()
    )
    for d in rows:
        deliver_once(db, d)


def build_task_event_payload(task: WorkTask, event: str, extra: dict = None) -> dict:
    payload = {
        "event": event,
        "task_id": task.task_id,
        "worker_id": task.worker_id,
        "biz_task_id": task.biz_task_id or "",
        "status": task.status.value if hasattr(task.status, "value") else task.status,
        "result": task.result or None,
        "tokens_used": task.tokens_used or 0,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
    }
    if extra:
        payload.update(extra)
    return payload
