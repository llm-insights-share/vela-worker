"""From vela-agent demo-* templates (non digital-worker): Duty → Role → onboard Workers.

Uses SINGLE/specialist agents as duty templates. COMPOSITE coordinators are skipped
(entry COMPOSITE is built by onboard_worker).
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from models import (
    Duty, DutyStatus, DigitalRole, DigitalWorker, RoleStatus, WorkerStatus, now_utc,
)
from routes.duties import _snapshot_from_agent
from services.vela_agent_client import vela_agent_client, VelaAgentError
from services.worker_service import onboard_worker


# Domain tag → (role config, worker config, duty specs keyed by agent name substring)
# Duty templates must be SINGLE specialists, not COMPOSITE coordinators.
DOMAIN_SPECS = {
    "demo-hr": {
        "role_id": "role-demo-hr",
        "role_name": "HR数字专员",
        "role_description": "制度问答、简历筛选与 HRIS 查询",
        "dept_id": "dept-hr",
        "worker_name": "HR助手",
        "duties": [
            {
                "duty_id": "duty-demo-hr-assistant",
                "name": "HR智能助手",
                "agent_name": "demo-hr-assistant",
                "task_types": ["hr.assistant", "hr.resume_screen", "hr.policy_qa"],
                "keywords": ["简历", "制度", "招聘", "HR", "人事"],
            },
        ],
    },
    "demo-audit": {
        "role_id": "role-demo-audit",
        "role_name": "经济责任审计助理",
        "role_description": "资料收集、风险识别与报告撰写",
        "dept_id": "dept-audit",
        "worker_name": "小审",
        "duties": [
            {
                "duty_id": "duty-material-collect",
                "name": "审计资料收集",
                "agent_name": "demo-audit-collector",
                "task_types": ["audit.material_collect"],
                "keywords": ["资料", "收集", "立项材料", "材料"],
            },
            {
                "duty_id": "duty-risk-scan",
                "name": "风险初筛",
                "agent_name": "demo-audit-risk",
                "task_types": ["audit.risk_scan"],
                "keywords": ["风险", "初筛", "排查", "风险点"],
            },
            {
                "duty_id": "duty-report-draft",
                "name": "报告初稿撰写",
                "agent_name": "demo-audit-reporter",
                "task_types": ["audit.report_draft"],
                "keywords": ["报告", "初稿", "撰写", "起草"],
            },
        ],
    },
    "demo-office": {
        "role_id": "role-demo-office",
        "role_name": "日常办公助理",
        "role_description": "会议督办、差旅报销与行政后勤",
        "dept_id": "dept-hq",
        "worker_name": "办公助手",
        "duties": [
            {
                "duty_id": "duty-demo-office-meeting",
                "name": "会议督办",
                "agent_name": "demo-office-meeting",
                "task_types": ["office.meeting"],
                "keywords": ["会议", "督办", "纪要"],
            },
            {
                "duty_id": "duty-demo-office-expense",
                "name": "差旅报销预审",
                "agent_name": "demo-office-expense",
                "task_types": ["office.expense"],
                "keywords": ["报销", "差旅", "费用"],
            },
            {
                "duty_id": "duty-demo-office-facility",
                "name": "行政后勤",
                "agent_name": "demo-office-facility",
                "task_types": ["office.facility"],
                "keywords": ["会议室", "用印", "物资", "行政"],
            },
        ],
    },
    "demo-pm": {
        "role_id": "role-demo-pm",
        "role_name": "产品经理助理",
        "role_description": "竞品调研、数据分析与 PRD 撰写",
        "dept_id": "dept-hq",
        "worker_name": "产品助手",
        "duties": [
            {
                "duty_id": "duty-demo-pm-research",
                "name": "调研竞品",
                "agent_name": "demo-pm-research",
                "task_types": ["pm.research"],
                "keywords": ["调研", "竞品", "市场"],
            },
            {
                "duty_id": "duty-demo-pm-analytics",
                "name": "产品数据分析",
                "agent_name": "demo-pm-analytics",
                "task_types": ["pm.analytics"],
                "keywords": ["数据", "分析", "指标"],
            },
            {
                "duty_id": "duty-demo-pm-prd",
                "name": "PRD撰写",
                "agent_name": "demo-pm-prd",
                "task_types": ["pm.prd"],
                "keywords": ["PRD", "需求", "产品文档"],
            },
        ],
    },
}


def _list_demo_templates() -> Dict[str, dict]:
    """agent_name → agent summary (excluding digital-worker clones)."""
    try:
        agents = vela_agent_client.list_agents(page_size=100, status="PUBLISHED") or []
    except Exception:
        agents = vela_agent_client.list_agents(page_size=100) or []

    by_name: Dict[str, dict] = {}
    for a in agents:
        tags = [str(t).lower() for t in (a.get("tags") or [])]
        if "digital-worker" in tags:
            continue
        if not any(t in tags or t.startswith("demo") for t in tags):
            # keep if name starts with demo-
            if not str(a.get("name") or "").startswith("demo-"):
                continue
        name = a.get("name") or ""
        if name:
            by_name[name] = a
    return by_name


def _apply_agent_snapshot(duty: Duty, agent_id: str, agent: dict):
    snap = _snapshot_from_agent(agent)
    # Prefer full agent if list payload is thin
    if not snap.get("agent_template", {}).get("model_service_id"):
        full = vela_agent_client.get_agent(agent_id)
        snap = _snapshot_from_agent(full)
        agent = full
    duty.template_agent_id = agent_id
    duty.template_agent_name = snap["template_agent_name"] or agent.get("name") or ""
    duty.agent_template = snap["agent_template"]
    duty.skill_pack_ids = snap["skill_pack_ids"]
    duty.tool_permissions = snap["tool_permissions"]
    duty.kb_ids = snap["kb_ids"]
    duty.governance = snap["governance"]
    if agent.get("description") and not (duty.description or "").strip():
        duty.description = agent.get("description") or ""


def ensure_duties_from_templates(db: Session, catalog: Dict[str, dict]) -> List[str]:
    """Create/update duties bound to specialist templates. Returns duty_ids created/updated."""
    touched: List[str] = []
    for domain, spec in DOMAIN_SPECS.items():
        for dspec in spec["duties"]:
            agent_meta = catalog.get(dspec["agent_name"])
            if not agent_meta:
                print(f"[seed-tpl] skip duty {dspec['name']}: agent {dspec['agent_name']} not found")
                continue
            agent_type = (agent_meta.get("agent_type") or "SINGLE").upper()
            if agent_type == "COMPOSITE":
                print(f"[seed-tpl] skip COMPOSITE as duty template: {dspec['agent_name']}")
                continue
            agent_id = agent_meta.get("agent_id") or ""
            if not agent_id:
                continue

            duty = db.query(Duty).filter(Duty.duty_id == dspec["duty_id"]).first()
            if not duty:
                # name uniqueness — reuse by name if id differs
                duty = db.query(Duty).filter(Duty.name == dspec["name"]).first()
            if not duty:
                duty = Duty(
                    duty_id=dspec["duty_id"],
                    name=dspec["name"],
                    description=agent_meta.get("description") or "",
                    status=DutyStatus.ACTIVE,
                )
                db.add(duty)
                db.flush()
            else:
                # Keep stable duty_id if found by name with different id
                pass

            duty.name = dspec["name"]
            duty.description = agent_meta.get("description") or duty.description or ""
            duty.task_types = dspec["task_types"]
            duty.keywords = dspec["keywords"]
            duty.status = DutyStatus.ACTIVE
            try:
                full = vela_agent_client.get_agent(agent_id)
                _apply_agent_snapshot(duty, agent_id, full)
            except VelaAgentError as e:
                print(f"[seed-tpl] failed to load agent {agent_id}: {e}")
                continue
            touched.append(duty.duty_id)
            print(f"[seed-tpl] duty ready: {duty.name} ← {duty.template_agent_name} ({agent_id[:8]}…)")
    db.commit()
    return touched


def ensure_roles(db: Session) -> Dict[str, str]:
    """Create/update roles with duty_ids. Returns domain → role_id."""
    result: Dict[str, str] = {}
    for domain, spec in DOMAIN_SPECS.items():
        duty_ids = []
        for dspec in spec["duties"]:
            duty = db.query(Duty).filter(Duty.duty_id == dspec["duty_id"]).first()
            if not duty:
                duty = db.query(Duty).filter(Duty.name == dspec["name"]).first()
            if duty and (duty.template_agent_id or "").strip():
                duty_ids.append(duty.duty_id)
        if not duty_ids:
            print(f"[seed-tpl] skip role {spec['role_name']}: no bound duties")
            continue

        role = db.query(DigitalRole).filter(DigitalRole.role_id == spec["role_id"]).first()
        if not role:
            role = db.query(DigitalRole).filter(DigitalRole.name == spec["role_name"]).first()
        if not role:
            role = DigitalRole(
                role_id=spec["role_id"],
                name=spec["role_name"],
                description=spec["role_description"],
                duty_ids=duty_ids,
                status=RoleStatus.ACTIVE,
                version=1,
            )
            db.add(role)
        else:
            role.name = spec["role_name"]
            role.description = spec["role_description"]
            role.duty_ids = duty_ids
            role.status = RoleStatus.ACTIVE
            role.version = (role.version or 1) + 1
        db.flush()
        result[domain] = role.role_id
        print(f"[seed-tpl] role ready: {role.name} duties={duty_ids}")
    db.commit()
    return result


def ensure_workers(db: Session, role_map: Dict[str, str]) -> List[DigitalWorker]:
    """Onboard one worker per domain if not already present by name+role."""
    workers: List[DigitalWorker] = []
    for domain, spec in DOMAIN_SPECS.items():
        role_id = role_map.get(domain)
        if not role_id:
            continue
        existing = (
            db.query(DigitalWorker)
            .filter(
                DigitalWorker.name == spec["worker_name"],
                DigitalWorker.role_id == role_id,
                DigitalWorker.status == WorkerStatus.ON_DUTY,
            )
            .first()
        )
        if existing and (existing.entry_agent_id or "").strip() and not existing.entry_agent_id.startswith("demo-"):
            print(f"[seed-tpl] worker exists: {existing.name} entry={existing.entry_agent_id[:8]}…")
            workers.append(existing)
            continue
        try:
            worker = onboard_worker(
                db,
                name=spec["worker_name"],
                role_id=role_id,
                dept_id=spec["dept_id"],
                remark=f"from-template:{domain}",
                actor_id="seed-demo-templates",
            )
            workers.append(worker)
            print(f"[seed-tpl] onboarded {worker.name} ({worker.employee_no}) entry={worker.entry_agent_id}")
        except Exception as e:
            print(f"[seed-tpl] onboard failed for {spec['worker_name']}: {e}")
    return workers


def seed_from_demo_templates(db: Session) -> dict:
    health = vela_agent_client.check_health()
    status = str(health.get("status") or "").lower()
    if status in ("unreachable", "error"):
        print(f"[seed-tpl] vela-agent not ready: {health}")
        return {"ok": False, "health": health}

    catalog = _list_demo_templates()
    print(f"[seed-tpl] catalog templates: {sorted(catalog.keys())}")

    duty_ids = ensure_duties_from_templates(db, catalog)
    role_map = ensure_roles(db)
    workers = ensure_workers(db, role_map)
    return {
        "ok": True,
        "duties": duty_ids,
        "roles": role_map,
        "workers": [
            {
                "worker_id": w.worker_id,
                "name": w.name,
                "employee_no": w.employee_no,
                "entry_agent_id": w.entry_agent_id,
                "role_id": w.role_id,
                "dept_id": w.dept_id,
            }
            for w in workers
        ],
    }


if __name__ == "__main__":
    from database import SessionLocal, init_db
    from seed import seed_if_empty

    init_db()
    db = SessionLocal()
    try:
        seed_if_empty(db)
        result = seed_from_demo_templates(db)
        print("RESULT:", result)
    finally:
        db.close()
