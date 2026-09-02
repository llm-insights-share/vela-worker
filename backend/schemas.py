from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# --- Org ---

class DepartmentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    parent_id: Optional[str] = None
    sort: int = 0


class DepartmentResponse(BaseModel):
    dept_id: str
    name: str
    parent_id: Optional[str] = None
    sort: int = 0
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class HumanUserCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    avatar: str = ""
    dept_id: Optional[str] = None
    title: str = ""
    role: str = "EMPLOYEE"
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None


class HumanUserResponse(BaseModel):
    user_id: str
    name: str
    avatar: str = ""
    dept_id: Optional[str] = None
    title: str = ""
    role: str = "EMPLOYEE"
    status: str = "ACTIVE"
    username: Optional[str] = None
    email: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# --- Auth (JWT) ---

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    user_id: str
    username: str
    email: str = ""
    name: str = ""
    display_name: str = ""
    avatar: str = ""
    avatar_url: str = ""
    title: str = ""
    dept_id: Optional[str] = None
    role: str = "EMPLOYEE"
    status: str = "ACTIVE"
    is_active: bool = True
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class RegisterIn(BaseModel):
    email: str
    username: str
    password: str = Field(..., min_length=6)
    display_name: str = ""


class ProfileUpdateIn(BaseModel):
    display_name: str = ""
    email: str
    title: str = ""


class PasswordUpdateIn(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6)


class AdminCreateUserIn(BaseModel):
    email: str
    username: str
    password: str = Field(..., min_length=6)
    display_name: str = ""
    role: str = "EMPLOYEE"
    dept_id: Optional[str] = None
    title: str = ""


class ActiveIn(BaseModel):
    is_active: bool


class RolesIn(BaseModel):
    role: str


# --- Duties ---

class DutyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str = ""
    task_types: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    template_agent_id: str = Field(..., min_length=1)
    governance: Dict[str, Any] = Field(default_factory=dict)


class DutyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    task_types: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    template_agent_id: Optional[str] = None
    governance: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


class DutyResponse(BaseModel):
    duty_id: str
    name: str
    description: str = ""
    task_types: List[str] = []
    keywords: List[str] = []
    template_agent_id: str = ""
    template_agent_name: str = ""
    agent_template: Dict[str, Any] = {}
    skill_pack_ids: List[str] = []
    tool_permissions: List[Dict[str, Any]] = []
    kb_ids: List[str] = []
    governance: Dict[str, Any] = {}
    status: str = "ACTIVE"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# --- Roles ---

class RoleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str = ""
    duty_scope: List[str] = Field(default_factory=list)
    out_of_scope: List[str] = Field(default_factory=list)
    duty_ids: List[str] = Field(default_factory=list)
    governance: Dict[str, Any] = Field(default_factory=dict)


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    duty_scope: Optional[List[str]] = None
    out_of_scope: Optional[List[str]] = None
    duty_ids: Optional[List[str]] = None
    governance: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


class RoleResponse(BaseModel):
    role_id: str
    name: str
    description: str = ""
    duty_scope: List[str] = []
    out_of_scope: List[str] = []
    duty_ids: List[str] = []
    duty_names: List[str] = []
    task_types: List[str] = []
    governance: Dict[str, Any] = {}
    version: int = 1
    status: str = "ACTIVE"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# --- Workers ---

class WorkerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    avatar: str = ""
    role_id: str
    dept_id: Optional[str] = None
    escalation_contact: Dict[str, Any] = Field(default_factory=dict)
    remark: str = ""


class WorkerUpdate(BaseModel):
    name: Optional[str] = None
    avatar: Optional[str] = None
    dept_id: Optional[str] = None
    escalation_contact: Optional[Dict[str, Any]] = None
    remark: Optional[str] = None
    status: Optional[str] = None


class PermissionOverrideRequest(BaseModel):
    tool_overrides: List[Dict[str, Any]] = Field(default_factory=list)
    kb_overrides: Dict[str, List[str]] = Field(default_factory=dict)
    governance_overrides: Dict[str, Any] = Field(default_factory=dict)
    duty_scope_override: Optional[List[str]] = None


class WorkerDutyAddRequest(BaseModel):
    duty_id: str
    is_primary: bool = False


class WorkerDutyAgentResponse(BaseModel):
    duty_id: str
    duty_name: str = ""
    agent_id: str = ""
    source: str = "ROLE"
    is_primary: bool = False
    status: str = "ACTIVE"
    task_types: List[str] = []
    keywords: List[str] = []


class WorkerResponse(BaseModel):
    worker_id: str
    employee_no: str
    name: str
    avatar: str = ""
    role_id: str
    role_version: int = 1
    role_name: str = ""
    dept_id: Optional[str] = None
    dept_name: str = ""
    entry_agent_id: str = ""
    reception_agent_id: str = ""
    duties: List[WorkerDutyAgentResponse] = []
    duty_count: int = 0
    primary_agent_id: str = ""
    permission_overrides: Dict[str, Any] = {}
    governance_overrides: Dict[str, Any] = {}
    escalation_contact: Dict[str, Any] = {}
    duty_scope_override: List[str] = []
    spec_revision: int = 1
    status: str = "ON_DUTY"
    remark: str = ""
    onboard_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PushRuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    trigger_type: str = Field(default="EVENT", pattern="^(CRON|EVENT)$")
    cron_expr: str = ""
    event_key: str = ""  # TASK_COMPLETED | NEED_HUMAN | MANUAL
    prompt_template: str = Field(..., min_length=1)
    channel: str = Field(default="IM", pattern="^(IM|WEBHOOK)$")
    conv_id: str = ""
    callback_url: str = ""
    enabled: bool = True


class PushRuleUpdate(BaseModel):
    name: Optional[str] = None
    trigger_type: Optional[str] = None
    cron_expr: Optional[str] = None
    event_key: Optional[str] = None
    prompt_template: Optional[str] = None
    channel: Optional[str] = None
    conv_id: Optional[str] = None
    callback_url: Optional[str] = None
    enabled: Optional[bool] = None


class PushRuleResponse(BaseModel):
    rule_id: str
    worker_id: str
    name: str = ""
    trigger_type: str = "EVENT"
    cron_expr: str = ""
    event_key: str = ""
    prompt_template: str = ""
    channel: str = "IM"
    conv_id: str = ""
    callback_url: str = ""
    enabled: bool = True
    last_run_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# --- Tasks ---

class TaskCreate(BaseModel):
    task_type: str = ""
    title: str = Field(..., min_length=1, max_length=256)
    instruction: str = Field(..., min_length=1)
    context: Dict[str, Any] = Field(default_factory=dict)
    priority: str = "NORMAL"
    deadline: Optional[datetime] = None
    callback_url: str = ""
    callback_events: List[str] = Field(default_factory=lambda: ["ACCEPTED", "NEED_HUMAN", "COMPLETED", "FAILED"])
    reporter: Dict[str, Any] = Field(default_factory=dict)
    conv_id: Optional[str] = None
    biz_task_id: str = ""


class TaskMessageCreate(BaseModel):
    message: str = Field(..., min_length=1)


class TaskResponse(BaseModel):
    task_id: str
    worker_id: str
    duty_id: Optional[str] = None
    source: str = "IM"
    task_type: str = ""
    title: str = ""
    instruction: str = ""
    context: Dict[str, Any] = {}
    priority: str = "NORMAL"
    deadline: Optional[datetime] = None
    status: str = "RECEIVED"
    status_detail: str = ""
    conv_id: Optional[str] = None
    app_id: Optional[str] = None
    biz_task_id: str = ""
    agent_session_id: str = ""
    progress_note: str = ""
    result: Dict[str, Any] = {}
    artifacts: List[Any] = []
    tokens_used: int = 0
    reporter: Dict[str, Any] = {}
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    timeline: List[Dict[str, Any]] = []

    model_config = {"from_attributes": True}


# --- IM ---

class MemberInput(BaseModel):
    member_type: str  # HUMAN / WORKER
    member_id: str


class ConversationCreate(BaseModel):
    type: str = "GROUP"  # DIRECT / GROUP
    name: str = ""
    members: List[MemberInput] = Field(default_factory=list)


class ConversationResponse(BaseModel):
    conv_id: str
    type: str
    name: str = ""
    avatar: str = ""
    owner_id: str = ""
    members: List[Dict[str, Any]] = []
    last_message: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1)
    msg_type: str = "text"
    mention_worker_ids: List[str] = Field(default_factory=list)
    as_task: bool = False
    task_type: str = ""
    task_title: str = ""
    attachment_ids: List[str] = Field(default_factory=list)


class ApprovalAction(BaseModel):
    approved: bool
    comment: str = ""
    otp_code: Optional[str] = None
    param_values: Optional[dict] = None


class MessageResponse(BaseModel):
    msg_id: str
    conv_id: str
    sender_type: str
    sender_id: str
    sender_name: str = ""
    msg_type: str = "text"
    content: Dict[str, Any] = {}
    ref_task_id: Optional[str] = None
    ref_approval_id: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class InfoReply(BaseModel):
    message: str = Field(..., min_length=1)


# --- Open Apps ---

class OpenAppCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    allowed_task_types: List[str] = Field(default_factory=list)
    default_callback_url: str = ""


class OpenAppResponse(BaseModel):
    app_id: str
    name: str
    api_key: str
    app_secret: str = ""  # only returned on create
    allowed_task_types: List[str] = []
    default_callback_url: str = ""
    status: str = "ACTIVE"
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[Any]


class InboxMessageResponse(BaseModel):
    message_id: str
    user_id: str
    title: str
    body: str = ""
    level: str = "info"
    link_path: str = ""
    related_type: str = ""
    related_id: str = ""
    is_read: bool = False
    read_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class InboxUnreadCountResponse(BaseModel):
    unread_count: int = 0
