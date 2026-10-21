import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Boolean, Date, DateTime, Text, ForeignKey, JSON, Enum as SAEnum, UniqueConstraint,
)
from database import Base


def gen_uuid():
    return str(uuid.uuid4())


def now_utc():
    return datetime.now(timezone.utc)


class WorkerStatus(str, enum.Enum):
    ON_DUTY = "ON_DUTY"
    SUSPENDED = "SUSPENDED"
    OFFBOARDED = "OFFBOARDED"


class RoleStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"


class DutyStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"


class WorkerDutySource(str, enum.Enum):
    ROLE = "ROLE"
    EXTRA = "EXTRA"


class WorkerDutyStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    REMOVED = "REMOVED"


class TaskStatus(str, enum.Enum):
    RECEIVED = "RECEIVED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    NEED_HUMAN = "NEED_HUMAN"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


class TaskSource(str, enum.Enum):
    IM = "IM"
    OPEN_API = "OPEN_API"
    BPM = "BPM"


class ProjectStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


class ProjectItemStatus(str, enum.Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    DELEGATED = "DELEGATED"
    SUSPENDED = "SUSPENDED"


class ProjectDocSource(str, enum.Enum):
    UPLOAD = "UPLOAD"
    AI_GENERATED = "AI_GENERATED"


class ProjectOwnerType(str, enum.Enum):
    HUMAN = "HUMAN"
    WORKER = "WORKER"


class ConvType(str, enum.Enum):
    DIRECT = "DIRECT"
    GROUP = "GROUP"


class MemberType(str, enum.Enum):
    HUMAN = "HUMAN"
    WORKER = "WORKER"


class UserRole(str, enum.Enum):
    PLATFORM_ADMIN = "PLATFORM_ADMIN"
    DEPT_ADMIN = "DEPT_ADMIN"
    EMPLOYEE = "EMPLOYEE"


class Department(Base):
    __tablename__ = "departments"

    dept_id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String(128), nullable=False)
    parent_id = Column(String, nullable=True)
    sort = Column(Integer, default=0)
    created_at = Column(DateTime, default=now_utc)


class HumanUser(Base):
    __tablename__ = "human_users"

    user_id = Column(String, primary_key=True, default=gen_uuid)
    username = Column(String(64), unique=True, nullable=True, index=True)
    email = Column(String(256), unique=True, nullable=True, index=True)
    hashed_password = Column(String(256), nullable=True)
    name = Column(String(128), nullable=False)
    avatar = Column(String(512), default="")
    dept_id = Column(String, ForeignKey("departments.dept_id"), nullable=True)
    title = Column(String(128), default="")
    role = Column(SAEnum(UserRole), default=UserRole.EMPLOYEE)
    status = Column(String(16), default="ACTIVE")
    created_at = Column(DateTime, default=now_utc)
    updated_at = Column(DateTime, default=now_utc, onupdate=now_utc)


class Duty(Base):
    """Global duty library: each duty maps to one vela-agent template."""
    __tablename__ = "duties"

    duty_id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String(128), unique=True, nullable=False, index=True)
    description = Column(Text, default="")
    task_types = Column(JSON, default=list)  # routing keys
    keywords = Column(JSON, default=list)  # IM auto-match keywords
    template_agent_id = Column(String, default="")  # vela-agent used as template
    template_agent_name = Column(String(256), default="")
    # Cached snapshot from template agent (refreshed on save / used as fallback)
    agent_template = Column(JSON, default=dict)
    skill_pack_ids = Column(JSON, default=list)
    tool_permissions = Column(JSON, default=list)
    kb_ids = Column(JSON, default=list)
    governance = Column(JSON, default=dict)
    status = Column(SAEnum(DutyStatus), default=DutyStatus.ACTIVE)
    created_at = Column(DateTime, default=now_utc)
    updated_at = Column(DateTime, default=now_utc, onupdate=now_utc)


class DigitalRole(Base):
    __tablename__ = "digital_roles"

    role_id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String(128), unique=True, nullable=False, index=True)
    description = Column(Text, default="")
    duty_scope = Column(JSON, default=list)
    out_of_scope = Column(JSON, default=list)
    duty_ids = Column(JSON, default=list)  # ordered list of duty_id
    governance = Column(JSON, default=dict)
    version = Column(Integer, default=1)
    status = Column(SAEnum(RoleStatus), default=RoleStatus.ACTIVE)
    created_at = Column(DateTime, default=now_utc)
    updated_at = Column(DateTime, default=now_utc, onupdate=now_utc)


class DigitalWorker(Base):
    __tablename__ = "digital_workers"

    worker_id = Column(String, primary_key=True, default=gen_uuid)
    employee_no = Column(String(32), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    avatar = Column(String(512), default="")
    role_id = Column(String, ForeignKey("digital_roles.role_id"), nullable=False)
    role_version = Column(Integer, default=1)
    dept_id = Column(String, ForeignKey("departments.dept_id"), nullable=True)
    entry_agent_id = Column(String, default="")  # COMPOSITE entry agent
    reception_agent_id = Column(String, default="")  # SINGLE receptionist for chitchat / OOS refusal
    permission_overrides = Column(JSON, default=dict)
    governance_overrides = Column(JSON, default=dict)
    escalation_contact = Column(JSON, default=dict)
    duty_scope_override = Column(JSON, default=list)
    spec_revision = Column(Integer, default=1)
    status = Column(SAEnum(WorkerStatus), default=WorkerStatus.ON_DUTY)
    remark = Column(Text, default="")
    onboard_at = Column(DateTime, default=now_utc)
    offboard_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=now_utc)
    updated_at = Column(DateTime, default=now_utc, onupdate=now_utc)


class WorkerDutyAgent(Base):
    """Worker x Duty -> independent Agent instance."""
    __tablename__ = "worker_duty_agents"
    __table_args__ = (
        UniqueConstraint("worker_id", "duty_id", name="uq_worker_duty"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    worker_id = Column(String, ForeignKey("digital_workers.worker_id"), nullable=False, index=True)
    duty_id = Column(String, ForeignKey("duties.duty_id"), nullable=False, index=True)
    agent_id = Column(String, default="")
    source = Column(SAEnum(WorkerDutySource), default=WorkerDutySource.ROLE)
    is_primary = Column(Boolean, default=False)
    status = Column(SAEnum(WorkerDutyStatus), default=WorkerDutyStatus.ACTIVE)
    created_at = Column(DateTime, default=now_utc)
    updated_at = Column(DateTime, default=now_utc, onupdate=now_utc)


class WorkerSpecHistory(Base):
    __tablename__ = "worker_spec_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    worker_id = Column(String, ForeignKey("digital_workers.worker_id"), nullable=False, index=True)
    spec_revision = Column(Integer, nullable=False)
    spec = Column(JSON, default=dict)
    changed_by = Column(String(128), default="")
    created_at = Column(DateTime, default=now_utc)


class WorkTask(Base):
    __tablename__ = "work_tasks"

    task_id = Column(String, primary_key=True, default=gen_uuid)
    worker_id = Column(String, ForeignKey("digital_workers.worker_id"), nullable=False, index=True)
    duty_id = Column(String, nullable=True, index=True)
    source = Column(SAEnum(TaskSource), default=TaskSource.IM)
    task_type = Column(String(128), default="")
    title = Column(String(256), default="")
    instruction = Column(Text, default="")
    context = Column(JSON, default=dict)
    priority = Column(String(16), default="NORMAL")
    deadline = Column(DateTime, nullable=True)
    status = Column(SAEnum(TaskStatus), default=TaskStatus.RECEIVED)
    status_detail = Column(Text, default="")
    conv_id = Column(String, nullable=True, index=True)
    app_id = Column(String, nullable=True)
    biz_task_id = Column(String(128), default="", index=True)
    callback_url = Column(String(1024), default="")
    callback_events = Column(JSON, default=list)
    agent_session_id = Column(String, default="")
    project_id = Column(String, ForeignKey("projects.project_id"), nullable=True, index=True)
    item_id = Column(String, ForeignKey("project_items.item_id"), nullable=True, index=True)
    progress_note = Column(Text, default="")
    progress_pct = Column(Integer, default=0)
    progress_steps = Column(JSON, default=list)
    result = Column(JSON, default=dict)
    artifacts = Column(JSON, default=list)
    tokens_used = Column(Integer, default=0)
    reporter = Column(JSON, default=dict)
    created_at = Column(DateTime, default=now_utc)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)


class TaskEvent(Base):
    __tablename__ = "task_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("work_tasks.task_id"), nullable=False, index=True)
    event = Column(String(64), nullable=False)
    detail = Column(JSON, default=dict)
    actor = Column(String(128), default="")
    created_at = Column(DateTime, default=now_utc)


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    delivery_id = Column(String, primary_key=True, default=gen_uuid)
    task_id = Column(String, ForeignKey("work_tasks.task_id"), nullable=False, index=True)
    event = Column(String(64), nullable=False)
    payload = Column(JSON, default=dict)
    url = Column(String(1024), nullable=False)
    status = Column(String(16), default="PENDING")  # PENDING/SUCCESS/FAILED
    attempts = Column(Integer, default=0)
    next_retry_at = Column(DateTime, nullable=True)
    last_error = Column(Text, default="")
    created_at = Column(DateTime, default=now_utc)


class Conversation(Base):
    __tablename__ = "conversations"

    conv_id = Column(String, primary_key=True, default=gen_uuid)
    type = Column(SAEnum(ConvType), default=ConvType.GROUP)
    name = Column(String(256), default="")
    avatar = Column(String(512), default="")
    owner_id = Column(String, default="")
    created_at = Column(DateTime, default=now_utc)


class ConversationMember(Base):
    __tablename__ = "conversation_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conv_id = Column(String, ForeignKey("conversations.conv_id"), nullable=False, index=True)
    member_type = Column(SAEnum(MemberType), nullable=False)
    member_id = Column(String, nullable=False, index=True)
    joined_at = Column(DateTime, default=now_utc)
    last_read_msg_id = Column(String, default="")


class Message(Base):
    __tablename__ = "messages"

    msg_id = Column(String, primary_key=True, default=gen_uuid)
    conv_id = Column(String, ForeignKey("conversations.conv_id"), nullable=False, index=True)
    sender_type = Column(SAEnum(MemberType), nullable=False)
    sender_id = Column(String, nullable=False)
    msg_type = Column(String(32), default="text")
    content = Column(JSON, default=dict)
    ref_task_id = Column(String, nullable=True, index=True)
    ref_approval_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=now_utc)


class WorkerImSession(Base):
    __tablename__ = "worker_im_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conv_id = Column(String, nullable=False, index=True)
    worker_id = Column(String, nullable=False, index=True)
    duty_id = Column(String, nullable=True, index=True)  # optional audit; routing uses entry agent
    agent_session_id = Column(String, default="")
    status = Column(String(16), default="ACTIVE")
    last_active_at = Column(DateTime, default=now_utc)


class WorkerPushRule(Base):
    """Proactive push / communication rules for a digital worker."""
    __tablename__ = "worker_push_rules"

    rule_id = Column(String, primary_key=True, default=gen_uuid)
    worker_id = Column(String, ForeignKey("digital_workers.worker_id"), nullable=False, index=True)
    name = Column(String(128), default="")
    trigger_type = Column(String(16), default="EVENT")  # CRON | EVENT
    cron_expr = Column(String(64), default="")
    event_key = Column(String(64), default="")  # TASK_COMPLETED | NEED_HUMAN | MANUAL
    prompt_template = Column(Text, default="")
    channel = Column(String(16), default="IM")  # IM | WEBHOOK
    conv_id = Column(String, default="")
    callback_url = Column(String(1024), default="")
    enabled = Column(Boolean, default=True)
    last_run_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=now_utc)
    updated_at = Column(DateTime, default=now_utc, onupdate=now_utc)


class OpenApp(Base):
    __tablename__ = "open_apps"

    app_id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String(128), nullable=False)
    api_key = Column(String(128), unique=True, nullable=False, index=True)
    api_key_hash = Column(String(128), default="")
    app_secret = Column(String(128), nullable=False)
    app_secret_hash = Column(String(128), default="")
    allowed_task_types = Column(JSON, default=list)
    default_callback_url = Column(String(1024), default="")
    status = Column(String(16), default="ACTIVE")
    created_at = Column(DateTime, default=now_utc)


class WorkerAuditLog(Base):
    __tablename__ = "worker_audit_logs"

    log_id = Column(String, primary_key=True, default=gen_uuid)
    worker_id = Column(String, index=True, default="")
    task_id = Column(String, index=True, default="")
    actor_type = Column(String(16), default="HUMAN")
    actor_id = Column(String(128), default="")
    action = Column(String(64), nullable=False)
    detail = Column(JSON, default=dict)
    created_at = Column(DateTime, default=now_utc)


class EmployeeCounter(Base):
    """工号序列"""
    __tablename__ = "employee_counters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    prefix = Column(String(8), unique=True, nullable=False)
    next_no = Column(Integer, default=10001)


class InboxMessage(Base):
    __tablename__ = "inbox_messages"
    __table_args__ = (
        UniqueConstraint("user_id", "related_type", "related_id", name="uq_inbox_user_related"),
    )

    message_id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, nullable=False, index=True)
    title = Column(String(256), nullable=False, default="")
    body = Column(Text, default="")
    level = Column(String(16), default="info")
    link_path = Column(String(512), default="")
    related_type = Column(String(64), default="")
    related_id = Column(String(128), default="")
    is_read = Column(Boolean, default=False, index=True)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=now_utc)


class Project(Base):
    __tablename__ = "projects"

    project_id = Column(String, primary_key=True, default=gen_uuid)
    owner_id = Column(String, ForeignKey("human_users.user_id"), nullable=False, index=True)
    name = Column(String(256), nullable=False)
    description = Column(Text, default="")
    status = Column(SAEnum(ProjectStatus), default=ProjectStatus.ACTIVE)
    progress_pct = Column(Integer, default=0)
    sort = Column(Integer, default=0)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=now_utc)
    updated_at = Column(DateTime, default=now_utc, onupdate=now_utc)


class ProjectItem(Base):
    __tablename__ = "project_items"

    item_id = Column(String, primary_key=True, default=gen_uuid)
    project_id = Column(String, ForeignKey("projects.project_id"), nullable=False, index=True)
    parent_id = Column(String, ForeignKey("project_items.item_id"), nullable=True, index=True)
    name = Column(String(256), nullable=False)
    description = Column(Text, default="")
    status = Column(SAEnum(ProjectItemStatus), default=ProjectItemStatus.TODO)
    sort = Column(Integer, default=0)
    worker_id = Column(String, ForeignKey("digital_workers.worker_id"), nullable=True, index=True)
    task_id = Column(String, ForeignKey("work_tasks.task_id"), nullable=True, index=True)
    progress_pct = Column(Integer, default=0)
    meta = Column(JSON, default=dict)
    planned_start = Column(DateTime, nullable=True)
    planned_end = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=now_utc)
    updated_at = Column(DateTime, default=now_utc, onupdate=now_utc)


class ProjectDocument(Base):
    __tablename__ = "project_documents"

    doc_id = Column(String, primary_key=True, default=gen_uuid)
    project_id = Column(String, ForeignKey("projects.project_id"), nullable=False, index=True)
    name = Column(String(512), nullable=False)
    file_path = Column(String(1024), default="")
    mime_type = Column(String(128), default="")
    size_bytes = Column(Integer, default=0)
    source = Column(SAEnum(ProjectDocSource), default=ProjectDocSource.UPLOAD)
    owner_type = Column(SAEnum(ProjectOwnerType), default=ProjectOwnerType.HUMAN)
    owner_id = Column(String, default="")
    owner_name = Column(String(128), default="")
    created_at = Column(DateTime, default=now_utc)
    updated_at = Column(DateTime, default=now_utc, onupdate=now_utc)


class ProjectActivity(Base):
    __tablename__ = "project_activities"

    activity_id = Column(String, primary_key=True, default=gen_uuid)
    project_id = Column(String, ForeignKey("projects.project_id"), nullable=False, index=True)
    kind = Column(String(64), default="update")
    text = Column(Text, default="")
    actor_type = Column(SAEnum(ProjectOwnerType), default=ProjectOwnerType.HUMAN)
    actor_id = Column(String, default="")
    actor_name = Column(String(128), default="")
    created_at = Column(DateTime, default=now_utc)
