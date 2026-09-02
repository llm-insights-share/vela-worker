"""Seed departments, human users, duties, and employee counter on first startup."""
from sqlalchemy.orm import Session

from auth_config import ADMIN_PASSWORD, ADMIN_USERNAME
from models import (
    Department, HumanUser, UserRole, EmployeeCounter, Duty, DutyStatus,
)
from security import hash_password

# Fixed seed users: user_id → (username, email)
SEED_USER_CREDS = {
    "u-admin": (ADMIN_USERNAME, f"{ADMIN_USERNAME}@localhost"),
    "u-zhang": ("zhang", "zhang@localhost"),
    "u-lisi": ("lisi", "lisi@localhost"),
    "u-wang": ("wang", "wang@localhost"),
}


def ensure_user_credentials(db: Session):
    """Backfill username/email/password for existing users missing credentials."""
    default_password = ADMIN_PASSWORD or "admin123"
    changed = False
    for user in db.query(HumanUser).all():
        if user.hashed_password and user.username:
            continue
        username, email = SEED_USER_CREDS.get(
            user.user_id,
            (f"user_{user.user_id[:8]}", f"{user.user_id[:8]}@localhost"),
        )
        # Avoid unique collisions if username already taken
        if not user.username:
            clash = db.query(HumanUser).filter(
                HumanUser.username == username,
                HumanUser.user_id != user.user_id,
            ).first()
            if clash:
                username = f"{username}_{user.user_id[:6]}"
            user.username = username
        if not user.email:
            clash_e = db.query(HumanUser).filter(
                HumanUser.email == email,
                HumanUser.user_id != user.user_id,
            ).first()
            if clash_e:
                email = f"{user.user_id[:8]}@localhost"
            user.email = email
        if not user.hashed_password:
            user.hashed_password = hash_password(default_password)
        changed = True
    if changed:
        db.commit()
        print("[seed] backfilled user credentials (default password applied)")


def seed_if_empty(db: Session):
    if db.query(Department).count() > 0:
        ensure_user_credentials(db)
        return

    depts = [
        Department(dept_id="dept-hq", name="总部", parent_id=None, sort=0),
        Department(dept_id="dept-audit", name="审计部", parent_id="dept-hq", sort=1),
        Department(dept_id="dept-finance", name="财务部", parent_id="dept-hq", sort=2),
        Department(dept_id="dept-hr", name="人力资源部", parent_id="dept-hq", sort=3),
    ]
    db.add_all(depts)

    pwd = hash_password(ADMIN_PASSWORD or "admin123")
    users = [
        HumanUser(
            user_id="u-admin",
            username=ADMIN_USERNAME,
            email=f"{ADMIN_USERNAME}@localhost",
            hashed_password=pwd,
            name="平台管理员",
            dept_id="dept-hq",
            title="平台管理员",
            role=UserRole.PLATFORM_ADMIN,
        ),
        HumanUser(
            user_id="u-zhang",
            username="zhang",
            email="zhang@localhost",
            hashed_password=pwd,
            name="张主管",
            dept_id="dept-audit",
            title="审计主管",
            role=UserRole.DEPT_ADMIN,
        ),
        HumanUser(
            user_id="u-lisi",
            username="lisi",
            email="lisi@localhost",
            hashed_password=pwd,
            name="李四",
            dept_id="dept-audit",
            title="审计专员",
            role=UserRole.EMPLOYEE,
        ),
        HumanUser(
            user_id="u-wang",
            username="wang",
            email="wang@localhost",
            hashed_password=pwd,
            name="王五",
            dept_id="dept-finance",
            title="财务专员",
            role=UserRole.EMPLOYEE,
        ),
    ]
    db.add_all(users)

    duties = [
        Duty(
            duty_id="duty-material-collect",
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
            status=DutyStatus.ACTIVE,
        ),
        Duty(
            duty_id="duty-risk-scan",
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
            status=DutyStatus.ACTIVE,
        ),
        Duty(
            duty_id="duty-report-draft",
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
            status=DutyStatus.ACTIVE,
        ),
    ]
    db.add_all(duties)

    db.add(EmployeeCounter(prefix="D", next_no=10001))
    db.commit()
    print("[seed] departments, users, duties, employee counter initialized")
