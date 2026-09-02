"""Build Worker Spec JSON from role + worker duties + overrides."""
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from models import (
    DigitalWorker, DigitalRole, Department, Duty, WorkerDutyAgent, WorkerDutyStatus,
)


def _merge_tools(duty_tools: List[dict], overrides: dict) -> List[dict]:
    tool_map = {}
    for t in duty_tools or []:
        tid = t.get("tool_id")
        if tid:
            tool_map[tid] = dict(t)
    for ov in (overrides or {}).get("tool_overrides") or []:
        tid = ov.get("tool_id")
        if not tid:
            continue
        base = tool_map.get(tid, {"tool_id": tid})
        base.update({k: v for k, v in ov.items() if v is not None})
        if ov.get("permission") == "denied":
            tool_map.pop(tid, None)
            continue
        tool_map[tid] = base
    return list(tool_map.values())


def _merge_kbs(duty_kbs: List[str], overrides: dict) -> List[str]:
    kb_set = set(duty_kbs or [])
    kb_ov = (overrides or {}).get("kb_overrides") or {}
    for kid in kb_ov.get("add") or []:
        kb_set.add(kid)
    for kid in kb_ov.get("remove") or []:
        kb_set.discard(kid)
    return list(kb_set)


def _merge_governance(duty_gov: dict, role_gov: dict, worker_gov: dict, overrides: dict) -> dict:
    gov = dict(duty_gov or {})
    gov.update(role_gov or {})
    gov.update(worker_gov or {})
    if (overrides or {}).get("governance_overrides"):
        gov.update(overrides["governance_overrides"])
    return gov


def list_active_worker_duties(db: Session, worker_id: str) -> List[Tuple[WorkerDutyAgent, Duty]]:
    rows = (
        db.query(WorkerDutyAgent, Duty)
        .join(Duty, Duty.duty_id == WorkerDutyAgent.duty_id)
        .filter(
            WorkerDutyAgent.worker_id == worker_id,
            WorkerDutyAgent.status == WorkerDutyStatus.ACTIVE,
        )
        .all()
    )
    # primary first, then ROLE, then EXTRA, stable by id
    def _key(item):
        wda, _ = item
        return (0 if wda.is_primary else 1, 0 if (wda.source.value if hasattr(wda.source, "value") else wda.source) == "ROLE" else 1, wda.id or 0)
    return sorted(rows, key=_key)


def resolve_duty_for_task_type(db: Session, worker: DigitalWorker, task_type: str) -> Optional[Tuple[WorkerDutyAgent, Duty]]:
    if not task_type:
        return None
    for wda, duty in list_active_worker_duties(db, worker.worker_id):
        if task_type in (duty.task_types or []):
            return wda, duty
    return None


def resolve_duty_for_text(db: Session, worker: DigitalWorker, text: str) -> Optional[Tuple[WorkerDutyAgent, Duty]]:
    """Match duty by keywords / task_types substrings; fallback to primary."""
    duties = list_active_worker_duties(db, worker.worker_id)
    if not duties:
        return None
    text_l = (text or "").lower()
    best = None
    best_score = 0
    for wda, duty in duties:
        score = 0
        for kw in (duty.keywords or []):
            if kw and kw.lower() in text_l:
                score += 2
        for tt in (duty.task_types or []):
            if tt and tt.lower() in text_l:
                score += 3
        if score > best_score:
            best_score = score
            best = (wda, duty)
    if best:
        return best
    for wda, duty in duties:
        if wda.is_primary:
            return wda, duty
    return duties[0]


def get_primary_worker_duty(db: Session, worker: DigitalWorker) -> Optional[Tuple[WorkerDutyAgent, Duty]]:
    duties = list_active_worker_duties(db, worker.worker_id)
    if not duties:
        return None
    for wda, duty in duties:
        if wda.is_primary:
            return wda, duty
    return duties[0]


def worker_task_types(db: Session, worker: DigitalWorker) -> List[str]:
    types = []
    seen = set()
    for _, duty in list_active_worker_duties(db, worker.worker_id):
        for t in (duty.task_types or []):
            if t not in seen:
                seen.add(t)
                types.append(t)
    return types


def role_task_types(db: Session, role: DigitalRole) -> List[str]:
    types = []
    seen = set()
    for did in (role.duty_ids or []):
        duty = db.query(Duty).filter(Duty.duty_id == did).first()
        if not duty:
            continue
        for t in (duty.task_types or []):
            if t not in seen:
                seen.add(t)
                types.append(t)
    return types


def effective_tool_bindings_for_duty(duty: Duty, worker: DigitalWorker) -> List[dict]:
    tools = _merge_tools(duty.tool_permissions or [], worker.permission_overrides or {})
    bindings = []
    for t in tools:
        if t.get("permission") == "denied":
            continue
        bindings.append({
            "tool_id": t["tool_id"],
            "require_approval": bool(t.get("require_approval", False)),
        })
    return bindings


def effective_kb_ids_for_duty(duty: Duty, worker: DigitalWorker, shared_kb_ids: List[str] = None) -> List[str]:
    kbs = _merge_kbs(duty.kb_ids or [], worker.permission_overrides or {})
    for kid in (shared_kb_ids or []):
        if kid not in kbs:
            kbs.append(kid)
    return kbs


def build_worker_spec(
    db: Session,
    worker: DigitalWorker,
    role: Optional[DigitalRole] = None,
) -> Dict[str, Any]:
    if role is None:
        role = db.query(DigitalRole).filter(DigitalRole.role_id == worker.role_id).first()
    dept = None
    if worker.dept_id:
        dept = db.query(Department).filter(Department.dept_id == worker.dept_id).first()

    overrides = worker.permission_overrides or {}
    duty_scope = worker.duty_scope_override or (role.duty_scope if role else [])
    role_gov = role.governance if role else {}

    capabilities = []
    all_task_types = []
    seen_tt = set()
    for wda, duty in list_active_worker_duties(db, worker.worker_id):
        tools = _merge_tools(duty.tool_permissions or [], overrides)
        kbs = _merge_kbs(duty.kb_ids or [], overrides)
        gov = _merge_governance(duty.governance or {}, role_gov, worker.governance_overrides or {}, overrides)
        tpl = duty.agent_template or {}
        for t in (duty.task_types or []):
            if t not in seen_tt:
                seen_tt.add(t)
                all_task_types.append(t)
        capabilities.append({
            "duty_id": duty.duty_id,
            "duty_name": duty.name,
            "source": wda.source.value if hasattr(wda.source, "value") else wda.source,
            "is_primary": bool(wda.is_primary),
            "role": "sub_agent",
            "agent_type": tpl.get("agent_type", "SINGLE"),
            "agent_id": wda.agent_id or "",
            "keywords": duty.keywords or [],
            "skills": [{"skill_pack_id": sid} for sid in (duty.skill_pack_ids or [])],
            "tools": tools,
            "knowledge_bases": [{"kb_id": kid} for kid in kbs],
            "task_types": duty.task_types or [],
            "governance": {
                "autonomy_level": gov.get("autonomy_level", "L2"),
                "token_budget_per_task": gov.get("token_budget_per_task", gov.get("token_budget", 100000)),
                "max_concurrent_tasks": gov.get("max_concurrent_tasks", 5),
            },
        })

    # aggregate governance from primary / role
    primary = next((c for c in capabilities if c.get("is_primary")), capabilities[0] if capabilities else None)
    agg_gov = (primary or {}).get("governance", {}) if primary else {}
    hitl = {}
    if primary:
        wda_primary = next((w for w, d in list_active_worker_duties(db, worker.worker_id) if w.is_primary), None)
        duty_primary = None
        if wda_primary:
            duty_primary = db.query(Duty).filter(Duty.duty_id == wda_primary.duty_id).first()
        if duty_primary:
            gov = _merge_governance(duty_primary.governance or {}, role_gov, worker.governance_overrides or {}, overrides)
            hitl = gov.get("hitl_policy", {})
            agg_gov = {
                "autonomy_level": gov.get("autonomy_level", "L2"),
                "hitl_policy": hitl,
                "token_budget_per_task": gov.get("token_budget_per_task", gov.get("token_budget", 100000)),
                "max_concurrent_tasks": gov.get("max_concurrent_tasks", 5),
                "escalation_contact": worker.escalation_contact or gov.get("escalation_contact", {}),
            }

    return {
        "spec_version": "1.1",
        "spec_revision": worker.spec_revision,
        "identity": {
            "worker_id": worker.worker_id,
            "employee_no": worker.employee_no,
            "name": worker.name,
            "avatar": worker.avatar or "",
            "employee_type": "DIGITAL",
            "dept_id": worker.dept_id or "",
            "dept_name": dept.name if dept else "",
            "role_name": role.name if role else "",
            "status": worker.status.value if hasattr(worker.status, "value") else worker.status,
            "onboard_date": worker.onboard_at.isoformat() if worker.onboard_at else None,
        },
        "entry_agent": {
            "agent_id": worker.entry_agent_id or "",
            "agent_type": "COMPOSITE",
            "role": "entry",
            "memory_enabled": True,
            "description": "入口协调 Agent：意图识别、职责调度与结果汇总；寒暄/拒答由基础接待子 Agent 承接",
            "reception_agent": {
                "agent_id": getattr(worker, "reception_agent_id", None) or "",
                "agent_type": "SINGLE",
                "role": "reception",
                "role_name": "基础接待",
                "description": "自我介绍、能力说明、历史对话续聊，以及对超职责意图的婉转拒答",
            },
        },
        "profile": {
            "description": role.description if role else "",
            "duty_scope": duty_scope,
            "out_of_scope": role.out_of_scope if role else [],
            "service_hours": "7x24",
            "languages": ["zh-CN"],
        },
        "capabilities": {
            "duties": capabilities,
            "task_types": all_task_types,
            "note": "duties 为入口 COMPOSITE 的子 Agent；调度关键词写入 composition",
        },
        "governance": agg_gov or {
            "autonomy_level": (role_gov or {}).get("autonomy_level", "L2"),
            "hitl_policy": {},
            "token_budget_per_task": 100000,
            "max_concurrent_tasks": 5,
            "escalation_contact": worker.escalation_contact or {},
        },
        "endpoints": {
            "task_dispatch": f"POST /api/v1/open/workers/{worker.worker_id}/tasks",
            "task_query": "GET /api/v1/open/tasks/{task_id}",
            "im_mention": f"@{worker.name}",
        },
    }
