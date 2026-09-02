from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import WorkerPushRule, DigitalWorker, HumanUser, gen_uuid, now_utc
from schemas import PushRuleCreate, PushRuleUpdate, PushRuleResponse
from deps import get_current_user, require_admin
from services import push_service

router = APIRouter(prefix="/api/v1/workers/{worker_id}/push-rules", tags=["push-rules"])


def _ensure_worker(db: Session, worker_id: str) -> DigitalWorker:
    worker = db.query(DigitalWorker).filter(DigitalWorker.worker_id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="数字员工不存在")
    return worker


@router.get("", response_model=List[PushRuleResponse])
def list_push_rules(
    worker_id: str,
    db: Session = Depends(get_db),
    user: HumanUser = Depends(get_current_user),
):
    _ensure_worker(db, worker_id)
    return (
        db.query(WorkerPushRule)
        .filter(WorkerPushRule.worker_id == worker_id)
        .order_by(WorkerPushRule.created_at.desc())
        .all()
    )


@router.post("", response_model=PushRuleResponse, status_code=201)
def create_push_rule(
    worker_id: str,
    data: PushRuleCreate,
    db: Session = Depends(get_db),
    user: HumanUser = Depends(require_admin),
):
    _ensure_worker(db, worker_id)
    if data.trigger_type == "CRON" and not (data.cron_expr or "").strip():
        raise HTTPException(status_code=400, detail="CRON 规则需要 cron_expr")
    if data.trigger_type == "EVENT" and not (data.event_key or "").strip():
        raise HTTPException(status_code=400, detail="EVENT 规则需要 event_key")
    if data.channel == "IM" and not (data.conv_id or "").strip():
        raise HTTPException(status_code=400, detail="IM 渠道需要 conv_id")
    if data.channel == "WEBHOOK" and not (data.callback_url or "").strip():
        raise HTTPException(status_code=400, detail="WEBHOOK 渠道需要 callback_url")

    rule = WorkerPushRule(
        rule_id=gen_uuid(),
        worker_id=worker_id,
        name=data.name,
        trigger_type=data.trigger_type,
        cron_expr=data.cron_expr or "",
        event_key=data.event_key or "",
        prompt_template=data.prompt_template,
        channel=data.channel,
        conv_id=data.conv_id or "",
        callback_url=data.callback_url or "",
        enabled=data.enabled,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.put("/{rule_id}", response_model=PushRuleResponse)
def update_push_rule(
    worker_id: str,
    rule_id: str,
    data: PushRuleUpdate,
    db: Session = Depends(get_db),
    user: HumanUser = Depends(require_admin),
):
    _ensure_worker(db, worker_id)
    rule = db.query(WorkerPushRule).filter(
        WorkerPushRule.rule_id == rule_id,
        WorkerPushRule.worker_id == worker_id,
    ).first()
    if not rule:
        raise HTTPException(status_code=404, detail="推送规则不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(rule, k, v)
    rule.updated_at = now_utc()
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/{rule_id}")
def delete_push_rule(
    worker_id: str,
    rule_id: str,
    db: Session = Depends(get_db),
    user: HumanUser = Depends(require_admin),
):
    rule = db.query(WorkerPushRule).filter(
        WorkerPushRule.rule_id == rule_id,
        WorkerPushRule.worker_id == worker_id,
    ).first()
    if not rule:
        raise HTTPException(status_code=404, detail="推送规则不存在")
    db.delete(rule)
    db.commit()
    return {"ok": True}


@router.post("/{rule_id}/run")
async def run_push_rule_now(
    worker_id: str,
    rule_id: str,
    db: Session = Depends(get_db),
    user: HumanUser = Depends(require_admin),
):
    rule = db.query(WorkerPushRule).filter(
        WorkerPushRule.rule_id == rule_id,
        WorkerPushRule.worker_id == worker_id,
    ).first()
    if not rule:
        raise HTTPException(status_code=404, detail="推送规则不存在")
    result = await push_service.execute_rule(db, rule, {"trigger": "MANUAL", "actor": user.user_id})
    return result
