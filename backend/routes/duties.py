from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from database import get_db
from models import Duty, DutyStatus, DigitalRole, now_utc, gen_uuid
from schemas import DutyCreate, DutyUpdate, DutyResponse, PaginatedResponse
from deps import require_admin, get_current_user
from models import HumanUser
from services.vela_agent_client import vela_agent_client, VelaAgentError

router = APIRouter(prefix="/api/v1/duties", tags=["duties"])


def _snapshot_from_agent(agent: dict) -> dict:
    """Cache skill/tool/kb/governance from a vela-agent for specs & cloning fallback."""
    tool_permissions = []
    for b in agent.get("tool_bindings") or []:
        tool_permissions.append({
            "tool_id": b.get("tool_id"),
            "permission": "allowed",
            "require_approval": bool(b.get("require_approval", False)),
            "name": b.get("name") or b.get("tool_id"),
        })
    if not tool_permissions:
        for tid in agent.get("tool_ids") or []:
            tool_permissions.append({"tool_id": tid, "permission": "allowed", "require_approval": False})
    return {
        "template_agent_name": agent.get("name") or "",
        "agent_template": {
            "agent_type": agent.get("agent_type") or "SINGLE",
            "model_service_id": agent.get("model_service_id") or "",
            "system_prompt_tpl": agent.get("system_prompt") or "",
            "max_iterations": agent.get("max_iterations", 10),
            "step_timeout_seconds": agent.get("step_timeout_seconds", 60),
        },
        "skill_pack_ids": agent.get("skill_pack_ids") or [],
        "tool_permissions": tool_permissions,
        "kb_ids": agent.get("knowledge_base_ids") or [],
        "governance": {
            "autonomy_level": agent.get("autonomy_level") or "L2",
            "token_budget_per_task": agent.get("token_budget") or 100000,
            "max_concurrent_tasks": agent.get("max_concurrent_sessions") or 5,
        },
    }


def _load_template_agent(template_agent_id: str) -> dict:
    try:
        return vela_agent_client.get_agent(template_agent_id)
    except VelaAgentError as e:
        raise HTTPException(status_code=400, detail=f"无法加载 vela-agent：{e}")


def _duty_dict(duty: Duty) -> dict:
    return {
        "duty_id": duty.duty_id,
        "name": duty.name,
        "description": duty.description or "",
        "task_types": duty.task_types or [],
        "keywords": duty.keywords or [],
        "template_agent_id": duty.template_agent_id or "",
        "template_agent_name": duty.template_agent_name or "",
        "agent_template": duty.agent_template or {},
        "skill_pack_ids": duty.skill_pack_ids or [],
        "tool_permissions": duty.tool_permissions or [],
        "kb_ids": duty.kb_ids or [],
        "governance": duty.governance or {},
        "status": duty.status.value if hasattr(duty.status, "value") else duty.status,
        "created_at": duty.created_at,
        "updated_at": duty.updated_at,
    }


def _apply_template(duty: Duty, template_agent_id: str, governance_override: dict = None):
    agent = _load_template_agent(template_agent_id)
    snap = _snapshot_from_agent(agent)
    duty.template_agent_id = template_agent_id
    duty.template_agent_name = snap["template_agent_name"]
    duty.agent_template = snap["agent_template"]
    duty.skill_pack_ids = snap["skill_pack_ids"]
    duty.tool_permissions = snap["tool_permissions"]
    duty.kb_ids = snap["kb_ids"]
    if governance_override:
        duty.governance = {**snap["governance"], **governance_override}
    else:
        duty.governance = snap["governance"]


@router.get("", response_model=PaginatedResponse)
def list_duties(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: HumanUser = Depends(get_current_user),
):
    q = db.query(Duty)
    if status:
        q = q.filter(Duty.status == status)
    total = q.count()
    items = q.order_by(Duty.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return PaginatedResponse(total=total, page=page, page_size=page_size, items=[_duty_dict(d) for d in items])


@router.post("", response_model=DutyResponse, status_code=201)
def create_duty(
    data: DutyCreate,
    db: Session = Depends(get_db),
    user: HumanUser = Depends(require_admin),
):
    if db.query(Duty).filter(Duty.name == data.name).first():
        raise HTTPException(status_code=400, detail="职责名已存在")
    duty = Duty(
        duty_id=gen_uuid(),
        name=data.name,
        description=data.description,
        task_types=data.task_types,
        keywords=data.keywords,
        status=DutyStatus.ACTIVE,
    )
    _apply_template(duty, data.template_agent_id, data.governance or None)
    db.add(duty)
    db.commit()
    db.refresh(duty)
    return _duty_dict(duty)


@router.get("/{duty_id}")
def get_duty(duty_id: str, db: Session = Depends(get_db), user: HumanUser = Depends(get_current_user)):
    duty = db.query(Duty).filter(Duty.duty_id == duty_id).first()
    if not duty:
        raise HTTPException(status_code=404, detail="职责不存在")
    return _duty_dict(duty)


@router.put("/{duty_id}")
def update_duty(
    duty_id: str,
    data: DutyUpdate,
    db: Session = Depends(get_db),
    user: HumanUser = Depends(require_admin),
):
    duty = db.query(Duty).filter(Duty.duty_id == duty_id).first()
    if not duty:
        raise HTTPException(status_code=404, detail="职责不存在")
    payload = data.model_dump(exclude_unset=True)
    if "name" in payload and payload["name"] != duty.name:
        if db.query(Duty).filter(Duty.name == payload["name"]).first():
            raise HTTPException(status_code=400, detail="职责名已存在")
    template_id = payload.pop("template_agent_id", None)
    governance = payload.pop("governance", None)
    for k, v in payload.items():
        if k == "status" and v:
            duty.status = DutyStatus(v)
        else:
            setattr(duty, k, v)
    if template_id:
        _apply_template(duty, template_id, governance)
    elif governance is not None:
        duty.governance = {**(duty.governance or {}), **governance}
    duty.updated_at = now_utc()
    db.commit()
    db.refresh(duty)
    return _duty_dict(duty)


@router.get("/{duty_id}/roles")
def list_duty_roles(duty_id: str, db: Session = Depends(get_db), user: HumanUser = Depends(get_current_user)):
    duty = db.query(Duty).filter(Duty.duty_id == duty_id).first()
    if not duty:
        raise HTTPException(status_code=404, detail="职责不存在")
    roles = db.query(DigitalRole).all()
    return [
        {"role_id": r.role_id, "name": r.name, "status": r.status.value if hasattr(r.status, "value") else r.status}
        for r in roles
        if duty_id in (r.duty_ids or [])
    ]
