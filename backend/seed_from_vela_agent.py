"""Sync duty templates from vela-agent and onboard demo digital workers with real agent IDs."""
from __future__ import annotations

from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from models import (
    Duty, DigitalRole, DigitalWorker, WorkerDutyAgent, Department,
    WorkerStatus, WorkerDutySource, WorkerDutyStatus, WorkerAuditLog, now_utc,
)
from seed_demo_workers import (
    DUTY_HR_RESUME, DUTY_HR_ANNOUNCE, DUTY_HR_INTERVIEW,
    DUTY_AUDIT_COLLECT, DUTY_AUDIT_RISK, DUTY_AUDIT_REPORT,
    ROLE_HR_RECRUITER, ROLE_HR_ANALYST, ROLE_AUDIT_ASSISTANT,
    WORKER_HIRE, WORKER_ANALYST, WORKER_XIAOSHEN,
)


def is_fake_agent_id(agent_id: Optional[str]) -> bool:
    aid = (agent_id or "").strip()
    return not aid or aid.startswith("demo-")


def _list_catalog_agents() -> list:
    try:
        from services.vela_agent_client import vela_agent_client
        health = vela_agent_client.check_health()
        status = str(health.get("status") or "").lower()
        if status in ("unreachable", "error"):
            print(f"[seed] vela-agent health={health}; skip agent sync/onboard")
            return []
        try:
            agents = vela_agent_client.list_agents(page_size=100, status="PUBLISHED") or []
        except Exception:
            agents = vela_agent_client.list_agents(page_size=100) or []
        return agents if isinstance(agents, list) else []
    except Exception as e:
        print(f"[seed] vela-agent unreachable: {e}")
        return []


def sync_duty_templates_from_agents(db: Session, agents: list = None) -> int:
    """Fill empty Duty.template_agent_id by keyword match against catalog agents."""
    agents = agents if agents is not None else _list_catalog_agents()
    if not agents:
        return 0

    def _pick(keywords: list[str]) -> Tuple[str, str]:
        for a in agents:
            name = (a.get("name") or "").lower()
            tags = " ".join(a.get("tags") or []).lower()
            blob = f"{name} {tags}"
            if any(k.lower() in blob for k in keywords):
                return a.get("agent_id") or "", a.get("name") or ""
        for a in agents:
            tags = " ".join(a.get("tags") or []).lower()
            if "digital-worker" in tags:
                continue
            aid = a.get("agent_id") or ""
            if aid:
                return aid, a.get("name") or ""
        return "", ""

    mapping = {
        DUTY_HR_RESUME: ["简历", "招聘", "resume", "hr"],
        DUTY_HR_ANNOUNCE: ["公告", "announce", "招聘"],
        DUTY_HR_INTERVIEW: ["面试", "interview"],
        DUTY_AUDIT_COLLECT: ["资料", "收集", "审计", "audit"],
        DUTY_AUDIT_RISK: ["风险", "risk", "审计"],
        DUTY_AUDIT_REPORT: ["报告", "report", "审计"],
    }
    changed = 0
    for duty_id, kws in mapping.items():
        duty = db.query(Duty).filter(Duty.duty_id == duty_id).first()
        if not duty:
            continue
        # Re-bind if empty or previously bound to a fake id
        if duty.template_agent_id and not is_fake_agent_id(duty.template_agent_id):
            continue
        aid, aname = _pick(kws)
        if aid:
            duty.template_agent_id = aid
            duty.template_agent_name = aname
            changed += 1
    if changed:
        db.commit()
        print(f"[seed] bound {changed} duty template_agent_id(s) from vela-agent")
    return changed


def purge_fake_agent_ids(db: Session) -> None:
    """Clear demo-* agent references so they cannot be used for execution."""
    workers = db.query(DigitalWorker).all()
    for w in workers:
        if is_fake_agent_id(w.entry_agent_id):
            w.entry_agent_id = ""
        if is_fake_agent_id(getattr(w, "reception_agent_id", None)):
            w.reception_agent_id = ""
    links = db.query(WorkerDutyAgent).all()
    for link in links:
        if is_fake_agent_id(link.agent_id):
            link.agent_id = ""
    duties = db.query(Duty).all()
    for d in duties:
        if is_fake_agent_id(d.template_agent_id):
            d.template_agent_id = ""
            d.template_agent_name = ""
    db.commit()


def _duties_for_role(db: Session, role: DigitalRole) -> List[Duty]:
    duties: List[Duty] = []
    for did in role.duty_ids or []:
        duty = db.query(Duty).filter(Duty.duty_id == did).first()
        if duty:
            duties.append(duty)
    return duties


def _role_ready_for_onboard(duties: List[Duty]) -> bool:
    return bool(duties) and all(
        (d.template_agent_id or "").strip() and not is_fake_agent_id(d.template_agent_id)
        for d in duties
    )


def ensure_onboarded_demo_worker(
    db: Session,
    *,
    worker_id: str,
    employee_no: str,
    name: str,
    role_id: str,
    dept_id: str,
) -> Optional[DigitalWorker]:
    """
    Ensure a fixed-id demo worker exists; onboard real agents when templates available.
    Never writes demo-* placeholder agent IDs.
    """
    from services.worker_service import (
        _create_and_publish_duty_agent,
        _ensure_entry_agent,
        save_spec_snapshot,
    )
    from services.vela_agent_client import VelaAgentError
    from fastapi import HTTPException

    role = db.query(DigitalRole).filter(DigitalRole.role_id == role_id).first()
    if not role:
        print(f"[seed] role missing for {name}: {role_id}")
        return None

    duties = _duties_for_role(db, role)

    worker = db.query(DigitalWorker).filter(DigitalWorker.worker_id == worker_id).first()
    if not worker:
        worker = DigitalWorker(
            worker_id=worker_id,
            employee_no=employee_no,
            name=name,
            role_id=role_id,
            dept_id=dept_id,
            entry_agent_id="",
            reception_agent_id="",
            status=WorkerStatus.ON_DUTY,
            remark="seed-demo-shell",
            onboard_at=now_utc(),
            spec_revision=1,
        )
        db.add(worker)
        db.flush()
        db.commit()
    else:
        worker.name = name
        worker.role_id = role_id
        worker.dept_id = dept_id or worker.dept_id
        worker.status = WorkerStatus.ON_DUTY
        if is_fake_agent_id(worker.entry_agent_id):
            worker.entry_agent_id = ""
        db.commit()

    # Ensure duty links exist (agent_id may be empty until onboard)
    if duties:
        for idx, duty in enumerate(duties):
            link = (
                db.query(WorkerDutyAgent)
                .filter(
                    WorkerDutyAgent.worker_id == worker_id,
                    WorkerDutyAgent.duty_id == duty.duty_id,
                )
                .first()
            )
            if not link:
                db.add(WorkerDutyAgent(
                    worker_id=worker_id,
                    duty_id=duty.duty_id,
                    agent_id="",
                    source=WorkerDutySource.ROLE,
                    is_primary=(idx == 0),
                    status=WorkerDutyStatus.ACTIVE,
                ))
            elif is_fake_agent_id(link.agent_id):
                link.agent_id = ""
                link.status = WorkerDutyStatus.ACTIVE
        db.commit()

    if not is_fake_agent_id(worker.entry_agent_id):
        return worker

    if not _role_ready_for_onboard(duties):
        print(f"[seed] skip onboard {name}: duties missing real template_agent_id")
        return worker

    dept_name = ""
    if dept_id:
        dept = db.query(Department).filter(Department.dept_id == dept_id).first()
        dept_name = dept.name if dept else ""

    try:
        for link in list(
            db.query(WorkerDutyAgent).filter(WorkerDutyAgent.worker_id == worker_id).all()
        ):
            db.delete(link)
        db.flush()

        agent_ids = []
        duty_agent_pairs = []
        for idx, duty in enumerate(duties):
            agent_id = _create_and_publish_duty_agent(
                employee_no=employee_no,
                worker_name=name,
                dept_id=dept_id,
                dept_name=dept_name,
                duty=duty,
                role=role,
            )
            agent_ids.append(agent_id)
            duty_agent_pairs.append((duty, agent_id))
            db.add(WorkerDutyAgent(
                worker_id=worker_id,
                duty_id=duty.duty_id,
                agent_id=agent_id,
                source=WorkerDutySource.ROLE,
                is_primary=(idx == 0),
                status=WorkerDutyStatus.ACTIVE,
            ))
        db.flush()
        entry_agent_id = _ensure_entry_agent(
            db, worker, role, duties, duty_agent_pairs=duty_agent_pairs,
        )
        worker.remark = "seed-from-vela-agent"
        save_spec_snapshot(db, worker, changed_by="seed")
        db.add(WorkerAuditLog(
            worker_id=worker_id,
            actor_type="HUMAN",
            actor_id="seed",
            action="ONBOARD",
            detail={
                "employee_no": employee_no,
                "duty_ids": [d.duty_id for d in duties],
                "agent_ids": agent_ids,
                "entry_agent_id": entry_agent_id,
                "source": "seed_from_vela_agent",
            },
        ))
        db.commit()
        db.refresh(worker)
        print(f"[seed] onboarded demo worker {name} entry={entry_agent_id}")
        return worker
    except (VelaAgentError, HTTPException, Exception) as e:
        db.rollback()
        print(f"[seed] onboard failed for {name}: {e}")
        return db.query(DigitalWorker).filter(DigitalWorker.worker_id == worker_id).first()


def ensure_demo_workers_from_vela(db: Session) -> dict:
    """
    Sync templates + onboard hire/analyst/xiaoshen.
    Returns {worker_id: DigitalWorker|None}.
    """
    purge_fake_agent_ids(db)
    agents = _list_catalog_agents()
    if agents:
        sync_duty_templates_from_agents(db, agents)
    else:
        print("[seed] no vela-agent catalog; demo workers will not get real agent IDs")

    results = {
        WORKER_HIRE: ensure_onboarded_demo_worker(
            db,
            worker_id=WORKER_HIRE,
            employee_no="D-DEMO-01",
            name="招聘助手",
            role_id=ROLE_HR_RECRUITER,
            dept_id="dept-hr",
        ),
        WORKER_ANALYST: ensure_onboarded_demo_worker(
            db,
            worker_id=WORKER_ANALYST,
            employee_no="D-DEMO-02",
            name="数据分析员",
            role_id=ROLE_HR_ANALYST,
            dept_id="dept-hr",
        ),
        WORKER_XIAOSHEN: ensure_onboarded_demo_worker(
            db,
            worker_id=WORKER_XIAOSHEN,
            employee_no="D-DEMO-03",
            name="小审",
            role_id=ROLE_AUDIT_ASSISTANT,
            dept_id="dept-audit",
        ),
    }
    return results


def worker_assignable(worker: Optional[DigitalWorker]) -> bool:
    return bool(worker and worker.status == WorkerStatus.ON_DUTY)


def worker_ready(worker: Optional[DigitalWorker]) -> bool:
    return worker_assignable(worker) and not is_fake_agent_id(worker.entry_agent_id)
