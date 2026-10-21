"""Seed demo duties (HR/audit), roles; onboard workers via vela-agent when reachable."""
from __future__ import annotations

from sqlalchemy.orm import Session

from models import (
    Duty, DutyStatus, DigitalRole, RoleStatus,
)

# Fixed IDs
DUTY_HR_RESUME = "duty-hr-resume"
DUTY_HR_ANNOUNCE = "duty-hr-announce"
DUTY_HR_INTERVIEW = "duty-hr-interview"
DUTY_AUDIT_COLLECT = "duty-material-collect"
DUTY_AUDIT_RISK = "duty-risk-scan"
DUTY_AUDIT_REPORT = "duty-report-draft"

ROLE_HR_RECRUITER = "role-hr-recruiter"
ROLE_HR_ANALYST = "role-hr-analyst"
ROLE_AUDIT_ASSISTANT = "role-audit-assistant"

WORKER_HIRE = "worker-hire"
WORKER_ANALYST = "worker-analyst"
WORKER_XIAOSHEN = "worker-xiaoshen"


def _ensure_duty(db: Session, duty_id: str, **kwargs) -> Duty:
    duty = db.query(Duty).filter(Duty.duty_id == duty_id).first()
    if duty:
        return duty
    duty = Duty(duty_id=duty_id, status=DutyStatus.ACTIVE, **kwargs)
    db.add(duty)
    db.flush()
    return duty


def _ensure_role(db: Session, role_id: str, name: str, duty_ids: list, description: str = "") -> DigitalRole:
    role = db.query(DigitalRole).filter(DigitalRole.role_id == role_id).first()
    if role:
        if role.duty_ids != duty_ids:
            role.duty_ids = duty_ids
        return role
    role = DigitalRole(
        role_id=role_id,
        name=name,
        description=description,
        duty_ids=duty_ids,
        status=RoleStatus.ACTIVE,
    )
    db.add(role)
    db.flush()
    return role


def seed_demo_duties_and_roles(db: Session):
    """Idempotent: HR + audit duties and roles (no fake agent IDs)."""
    _ensure_duty(
        db,
        DUTY_HR_RESUME,
        name="简历筛选",
        description="根据岗位条件筛选候选人简历并输出通过名单",
        task_types=["hr.resume_screen"],
        keywords=["简历", "筛选", "候选人", "校招"],
        template_agent_id="",
        template_agent_name="",
        agent_template={},
        skill_pack_ids=[],
        tool_permissions=[],
        kb_ids=[],
        governance={"autonomy_level": "L2", "token_budget_per_task": 100000, "max_concurrent_tasks": 5},
    )
    _ensure_duty(
        db,
        DUTY_HR_ANNOUNCE,
        name="招聘公告撰写",
        description="起草与发布招聘公告",
        task_types=["hr.announce"],
        keywords=["公告", "发布", "招聘启事"],
        template_agent_id="",
        template_agent_name="",
        agent_template={},
        skill_pack_ids=[],
        tool_permissions=[],
        kb_ids=[],
        governance={"autonomy_level": "L2", "token_budget_per_task": 80000, "max_concurrent_tasks": 3},
    )
    _ensure_duty(
        db,
        DUTY_HR_INTERVIEW,
        name="面试组织",
        description="安排面试流程并整理评估材料",
        task_types=["hr.interview"],
        keywords=["面试", "评估", "安排"],
        template_agent_id="",
        template_agent_name="",
        agent_template={},
        skill_pack_ids=[],
        tool_permissions=[],
        kb_ids=[],
        governance={"autonomy_level": "L2", "token_budget_per_task": 80000, "max_concurrent_tasks": 3},
    )
    _ensure_duty(
        db,
        DUTY_AUDIT_COLLECT,
        name="审计资料收集",
        description="负责经济责任审计立项资料收集与整理",
        task_types=["audit.material_collect"],
        keywords=["资料", "收集", "立项材料", "材料"],
        template_agent_id="",
        template_agent_name="",
        agent_template={},
        skill_pack_ids=[],
        tool_permissions=[],
        kb_ids=[],
        governance={"autonomy_level": "L2", "token_budget_per_task": 100000, "max_concurrent_tasks": 5},
    )
    _ensure_duty(
        db,
        DUTY_AUDIT_RISK,
        name="风险初筛",
        description="对被审计对象进行风险初筛与提示",
        task_types=["audit.risk_scan"],
        keywords=["风险", "初筛", "排查", "风险点"],
        template_agent_id="",
        template_agent_name="",
        agent_template={},
        skill_pack_ids=[],
        tool_permissions=[],
        kb_ids=[],
        governance={"autonomy_level": "L2", "token_budget_per_task": 100000, "max_concurrent_tasks": 3},
    )
    _ensure_duty(
        db,
        DUTY_AUDIT_REPORT,
        name="报告初稿撰写",
        description="撰写审计报告初稿",
        task_types=["audit.report_draft"],
        keywords=["报告", "初稿", "撰写", "起草"],
        template_agent_id="",
        template_agent_name="",
        agent_template={},
        skill_pack_ids=[],
        tool_permissions=[],
        kb_ids=[],
        governance={"autonomy_level": "L2", "token_budget_per_task": 120000, "max_concurrent_tasks": 2},
    )
    db.commit()

    _ensure_role(
        db,
        ROLE_HR_RECRUITER,
        "校园招聘专员",
        [DUTY_HR_RESUME, DUTY_HR_ANNOUNCE, DUTY_HR_INTERVIEW],
        description="负责校园招聘全流程执行",
    )
    _ensure_role(
        db,
        ROLE_HR_ANALYST,
        "招聘数据分析员",
        [DUTY_HR_RESUME],
        description="负责招聘数据分析与报告",
    )
    _ensure_role(
        db,
        ROLE_AUDIT_ASSISTANT,
        "经济责任审计助理",
        [DUTY_AUDIT_COLLECT, DUTY_AUDIT_RISK, DUTY_AUDIT_REPORT],
        description="协助经济责任审计资料、风险与报告工作",
    )
    db.commit()


def seed_demo_workers(db: Session):
    """Duties/roles + sync/onboard from vela-agent (no demo-* agent IDs)."""
    seed_demo_duties_and_roles(db)
    from seed_from_vela_agent import ensure_demo_workers_from_vela
    ensure_demo_workers_from_vela(db)
    print("[seed] demo duties/roles ready; workers onboarded when vela-agent available")
