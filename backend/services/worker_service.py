"""Digital worker lifecycle: onboard, duties, permissions, suspend/offboard."""
from typing import List, Optional, Tuple
from fastapi import HTTPException
from sqlalchemy.orm import Session
from models import (
    DigitalWorker, DigitalRole, Department, Duty, DutyStatus, EmployeeCounter,
    WorkerSpecHistory, WorkerAuditLog, WorkerStatus, WorkerDutyAgent,
    WorkerDutySource, WorkerDutyStatus, gen_uuid, now_utc,
)
from config import SHARED_KB_IDS, ENTRY_MODEL_SERVICE_ID
from services.vela_agent_client import vela_agent_client, VelaAgentError
from services.spec_builder import (
    build_worker_spec, list_active_worker_duties, effective_tool_bindings_for_duty,
    effective_kb_ids_for_duty, role_task_types,
)


def allocate_employee_no(db: Session) -> str:
    counter = db.query(EmployeeCounter).filter(EmployeeCounter.prefix == "D").first()
    if not counter:
        counter = EmployeeCounter(prefix="D", next_no=10001)
        db.add(counter)
        db.flush()
    no = counter.next_no
    counter.next_no = no + 1
    return f"D-{no}"


def _render_prompt(template: str, worker_name: str, dept_name: str, duty_name: str, duty_scope, out_of_scope) -> str:
    text = (
        (template or "")
        .replace("{{worker_name}}", worker_name)
        .replace("{{dept_name}}", dept_name)
        .replace("{{duty_name}}", duty_name)
    )
    duty = "\n".join(f"- {d}" for d in (duty_scope or []))
    out = "\n".join(f"- {d}" for d in (out_of_scope or []))
    extra = ""
    if duty:
        extra += f"\n\n## 职责范围\n{duty}"
    if out:
        extra += f"\n\n## 超出范围（请礼貌拒绝）\n{out}"
    return text + extra


def _pick_model_service_id(tpl: dict) -> str:
    model_service_id = (tpl or {}).get("model_service_id")
    if model_service_id:
        return model_service_id
    try:
        services = vela_agent_client.list_model_services()
        if services:
            return services[0].get("model_service_id") or services[0].get("id")
    except VelaAgentError as e:
        raise HTTPException(status_code=502, detail=f"无法连接 vela-agent: {e}")
    return ""


def _clone_payload_from_template(
    *,
    template: dict,
    employee_no: str,
    worker_name: str,
    dept_id: Optional[str],
    dept_name: str,
    duty: Duty,
    role: Optional[DigitalRole],
    worker_overrides: dict = None,
    worker_gov_overrides: dict = None,
) -> dict:
    role_gov = (role.governance if role else {}) or {}
    duty_gov = duty.governance or {}
    gov = {
        "autonomy_level": template.get("autonomy_level") or "L2",
        "token_budget_per_task": template.get("token_budget") or 100000,
        "max_concurrent_tasks": template.get("max_concurrent_sessions") or 5,
        **duty_gov,
        **role_gov,
        **(worker_gov_overrides or {}),
    }

    duty_scope = (role.duty_scope if role else []) or [duty.name]
    out_of_scope = (role.out_of_scope if role else []) or []
    base_prompt = template.get("system_prompt") or f"你是数字员工{worker_name}，当前职责是「{duty.name}」。"
    # Treat template prompt as system_prompt_tpl so {{worker_name}} etc. can be substituted
    system_prompt = _render_prompt(
        base_prompt, worker_name, dept_name, duty.name, duty_scope, out_of_scope,
    )

    skill_ids = list(template.get("skill_pack_ids") or duty.skill_pack_ids or [])
    shared = list(SHARED_KB_IDS)
    kb_ids = list(dict.fromkeys((template.get("knowledge_base_ids") or duty.kb_ids or []) + shared))

    tool_bindings = []
    for b in template.get("tool_bindings") or []:
        if b.get("tool_id"):
            tool_bindings.append({
                "tool_id": b["tool_id"],
                "require_approval": bool(b.get("require_approval", False)),
            })
    if not tool_bindings and duty.tool_permissions:
        tool_bindings = [
            {"tool_id": t["tool_id"], "require_approval": bool(t.get("require_approval", False))}
            for t in duty.tool_permissions
            if t.get("tool_id") and t.get("permission") != "denied"
        ]
    if worker_overrides:
        fake_worker = type("W", (), {"permission_overrides": worker_overrides})()
        # Prefer duty cached tools + overrides
        tool_bindings = effective_tool_bindings_for_duty(duty, fake_worker)
        kb_ids = effective_kb_ids_for_duty(duty, fake_worker, shared)

    model_service_id = template.get("model_service_id") or _pick_model_service_id(duty.agent_template or {})
    if not model_service_id:
        raise HTTPException(status_code=400, detail=f"职责「{duty.name}」对应的模板 Agent 无模型服务")

    agent_name = f"DW-{employee_no}-{worker_name}-{duty.name}"
    return {
        "name": agent_name[:120],
        "description": duty.description or template.get("description") or f"{worker_name} · {duty.name}",
        "model_service_id": model_service_id,
        "system_prompt": system_prompt,
        "dept_id": dept_id or template.get("dept_id") or "",
        "autonomy_level": gov.get("autonomy_level", "L2"),
        "max_concurrent_sessions": gov.get("max_concurrent_tasks", 5),
        "token_budget": gov.get("token_budget_per_task", gov.get("token_budget", 100000)),
        "agent_type": template.get("agent_type") or (duty.agent_template or {}).get("agent_type", "SINGLE"),
        "max_iterations": template.get("max_iterations", 10),
        "step_timeout_seconds": template.get("step_timeout_seconds", 60),
        "skill_pack_ids": skill_ids,
        "knowledge_base_ids": kb_ids,
        "tool_bindings": tool_bindings,
        "tags": ["digital-worker", employee_no, duty.duty_id],
        "memory_enabled": bool(template.get("memory_enabled", True)),
    }


def _create_and_publish_duty_agent(
    *,
    employee_no: str,
    worker_name: str,
    dept_id: Optional[str],
    dept_name: str,
    duty: Duty,
    role: Optional[DigitalRole],
    worker_overrides: dict = None,
    worker_gov_overrides: dict = None,
) -> str:
    if not duty.template_agent_id:
        raise HTTPException(status_code=400, detail=f"职责「{duty.name}」未选择 vela-agent 模板，请先在职责管理中配置")

    try:
        template = vela_agent_client.get_agent(duty.template_agent_id)
    except VelaAgentError as e:
        raise HTTPException(status_code=502, detail=f"无法加载职责「{duty.name}」的模板 Agent: {e}")

    agent_payload = _clone_payload_from_template(
        template=template,
        employee_no=employee_no,
        worker_name=worker_name,
        dept_id=dept_id,
        dept_name=dept_name,
        duty=duty,
        role=role,
        worker_overrides=worker_overrides,
        worker_gov_overrides=worker_gov_overrides,
    )

    try:
        agent = vela_agent_client.create_agent(agent_payload)
        agent_id = agent["agent_id"]
        if agent_payload.get("skill_pack_ids"):
            vela_agent_client.bind_skills(agent_id, agent_payload["skill_pack_ids"])
        if agent_payload.get("knowledge_base_ids"):
            vela_agent_client.bind_knowledge_bases(agent_id, agent_payload["knowledge_base_ids"])
        if agent_payload.get("tool_bindings"):
            vela_agent_client.bind_tools(agent_id, agent_payload["tool_bindings"])
        try:
            vela_agent_client.update_agent(agent_id, {
                "memory_enabled": agent_payload.get("memory_enabled", True),
                "change_summary": "enable memory",
            })
        except Exception:
            pass
        vela_agent_client.validate_agent(agent_id)
        vela_agent_client.publish_agent(agent_id, f"数字员工 {worker_name} 职责 {duty.name}")
        return agent_id
    except VelaAgentError as e:
        raise HTTPException(status_code=502, detail=f"vela-agent 创建职责 Agent 失败（{duty.name}）: {e}")


def _duty_list_block(duties: List[Duty]) -> str:
    duty_lines = []
    for d in duties:
        kws = ", ".join((d.keywords or []) + (d.task_types or [])) or "—"
        duty_lines.append(f"- {d.name}：{(d.description or '').strip() or '无描述'}；调度关键词：{kws}")
    return "\n".join(duty_lines) if duty_lines else "- （暂无职责）"


def _build_entry_system_prompt(worker_name: str, employee_no: str, dept_name: str, role: DigitalRole, duties: List[Duty]) -> str:
    duty_block = _duty_list_block(duties)
    return (
        f"你是数字员工「{worker_name}」（工号 {employee_no}）的入口协调 Agent。\n"
        f"所属部门：{dept_name or '未分配'}；角色：{role.name}。\n\n"
        f"你负责识别用户意图并路由：\n"
        f"- 基础会话（自我介绍、能力范围、寒暄、结合近期对话的简短追问）→ 调度「基础接待」子 Agent；\n"
        f"- 职责内专业请求 → 调度匹配的职责子 Agent，再汇总答复；\n"
        f"- 明显超出全部职责 → 调度「基础接待」做婉转拒答，不要臆造专业结论。\n\n"
        f"当前可调度的专业职责（子 Agent）：\n{duty_block}\n\n"
        f"原则：\n"
        f"1. 寒暄/介绍/「你能做什么」等优先给「基础接待」，不要强行派给专业职责 Agent。\n"
        f"2. 超职责请求不编造答案，礼貌说明边界并提示可处理范围或转人工。\n"
        f"3. 多职责协作时整合各方结果，给出清晰、可执行的最终答复。\n"
        f"4. 结合消息中的【近期对话】理解指代与上下文，不编造未发生的事实。\n"
        f"5. 遵守企业合规与权限边界。\n"
    )


def _build_reception_system_prompt(
    worker_name: str,
    employee_no: str,
    dept_name: str,
    role: DigitalRole,
    duties: List[Duty],
) -> str:
    duty_block = _duty_list_block(duties)
    return (
        f"你是数字员工「{worker_name}」（工号 {employee_no}），以第一人称与用户沟通。\n"
        f"所属部门：{dept_name or '未分配'}；角色：{role.name}。\n\n"
        f"你的定位是「基础接待」：完成自我介绍、说明能力范围、承接闲聊与感谢/道别，"
        f"并在用户请求明显不属于专业职责时婉转拒答。\n\n"
        f"我当前可承担的专业职责：\n{duty_block}\n\n"
        f"回复要求：\n"
        f"1. 自我介绍时简洁说明身份、部门/角色，以及上述职责能帮用户做什么。\n"
        f"2. 若消息含【近期对话】，请结合上下文续聊，不要假装记得未出现的内容。\n"
        f"3. 对超出职责的请求：先肯定用户需求，明确说明这不在我的职责范围内，"
        f"再简要列出我能协助的方向，必要时建议联系人工同事或调整职责配置；不要编造专业答案。\n"
        f"4. 语气友好、专业、简洁；不要声称自己是通用大模型或无所不能。\n"
        f"5. 遵守企业合规与权限边界。\n"
    )


RECEPTION_TASK_KEYWORDS = [
    "你好", "您好", "嗨", "介绍", "自我介绍", "你是谁", "你是谁啊",
    "能做什么", "你会什么", "能力", "职责", "范围", "谢谢", "感谢",
    "再见", "拜拜", "闲聊", "帮忙", "能不能", "超出职责", "做不到",
    "帮我做别的", "其他事情", "转人工",
]


def _resolve_entry_model_service_id(role: Optional[DigitalRole]) -> str:
    if ENTRY_MODEL_SERVICE_ID:
        return ENTRY_MODEL_SERVICE_ID
    gov = (role.governance if role else None) or {}
    mid = gov.get("model_service_id") or ""
    if mid:
        return mid
    try:
        services = vela_agent_client.list_model_services()
    except VelaAgentError as e:
        raise HTTPException(status_code=502, detail=f"无法连接 vela-agent: {e}")
    if not services:
        raise HTTPException(status_code=400, detail="无可用模型服务，请配置 ENTRY_MODEL_SERVICE_ID 或注册模型服务")
    return services[0].get("model_service_id") or services[0].get("service_id") or services[0].get("id") or ""


def _duty_task_keywords(duty: Duty) -> List[str]:
    seen = set()
    out = []
    for x in (duty.keywords or []) + (duty.task_types or []):
        s = str(x).strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _ensure_reception_agent(
    worker: DigitalWorker,
    role: DigitalRole,
    duties: List[Duty],
    *,
    dept_name: str,
    model_service_id: str,
) -> str:
    """Create or update the per-worker reception SINGLE agent; return agent_id."""
    reception_name = f"DW-{worker.employee_no}-{worker.name}-接待"
    system_prompt = _build_reception_system_prompt(
        worker.name, worker.employee_no, dept_name, role, duties,
    )
    reception_id = (worker.reception_agent_id or "").strip()

    if reception_id:
        try:
            info = vela_agent_client.get_agent(reception_id)
            status = (info.get("status") or "").upper()
            if status == "DEPRECATED":
                try:
                    vela_agent_client.republish_agent(reception_id)
                except Exception:
                    pass
            vela_agent_client.update_agent(reception_id, {
                "name": reception_name[:120],
                "description": f"数字员工 {worker.name} 基础接待（寒暄/介绍/超职责拒答）",
                "system_prompt": system_prompt,
                "dept_id": worker.dept_id or "",
                "change_summary": "sync reception prompt",
            })
            try:
                vela_agent_client.set_memory_enabled(reception_id, True)
            except Exception:
                pass
            if SHARED_KB_IDS:
                try:
                    vela_agent_client.bind_knowledge_bases(reception_id, list(SHARED_KB_IDS))
                except Exception:
                    pass
            return reception_id
        except Exception:
            # fall through to create
            reception_id = ""

    try:
        created = vela_agent_client.create_agent({
            "name": reception_name[:120],
            "description": f"数字员工 {worker.name} 基础接待（寒暄/介绍/超职责拒答）",
            "agent_type": "SINGLE",
            "model_service_id": model_service_id,
            "system_prompt": system_prompt,
            "dept_id": worker.dept_id or "",
            "autonomy_level": (role.governance or {}).get("autonomy_level", "L2"),
            "knowledge_base_ids": list(SHARED_KB_IDS),
            "tags": ["digital-worker", "reception", worker.employee_no],
        })
        reception_id = created["agent_id"]
        if SHARED_KB_IDS:
            vela_agent_client.bind_knowledge_bases(reception_id, list(SHARED_KB_IDS))
        try:
            vela_agent_client.set_memory_enabled(reception_id, True)
        except Exception:
            pass
        vr = vela_agent_client.validate_agent(reception_id)
        ok = vr.get("valid", vr.get("passed", True))
        if not ok:
            raise HTTPException(status_code=400, detail=f"接待 Agent 校验失败: {vr.get('errors') or vr}")
        vela_agent_client.publish_agent(reception_id, f"数字员工 {worker.name} 接待 Agent")
        worker.reception_agent_id = reception_id
        return reception_id
    except HTTPException:
        raise
    except VelaAgentError as e:
        # Name collision: try rename-free update path via unique suffix
        if getattr(e, "status_code", None) == 409:
            suffix_name = f"{reception_name[:100]}-{worker.worker_id[:8]}"
            created = vela_agent_client.create_agent({
                "name": suffix_name[:120],
                "description": f"数字员工 {worker.name} 基础接待（寒暄/介绍/超职责拒答）",
                "agent_type": "SINGLE",
                "model_service_id": model_service_id,
                "system_prompt": system_prompt,
                "dept_id": worker.dept_id or "",
                "autonomy_level": (role.governance or {}).get("autonomy_level", "L2"),
                "knowledge_base_ids": list(SHARED_KB_IDS),
                "tags": ["digital-worker", "reception", worker.employee_no],
            })
            reception_id = created["agent_id"]
            try:
                vela_agent_client.set_memory_enabled(reception_id, True)
            except Exception:
                pass
            vela_agent_client.validate_agent(reception_id)
            vela_agent_client.publish_agent(reception_id, f"数字员工 {worker.name} 接待 Agent")
            worker.reception_agent_id = reception_id
            return reception_id
        raise HTTPException(status_code=502, detail=f"创建接待 Agent 失败: {e}")


def _reception_role_description(duties: List[Duty]) -> str:
    names = "、".join(d.name for d in duties) if duties else "（暂无专业职责）"
    return (
        "负责寒暄、自我介绍、能力范围说明、结合近期对话的简短续聊，"
        f"以及对明显不属于专业职责（{names}）的请求做婉转拒答。"
        "不要回答专业职责内应由对应子 Agent 处理的深度问题。"
    )


def _dbg_entry(hypothesis_id, location, message, data=None, run_id="post-fix"):
    # #region agent log
    try:
        import json as _json, time as _time
        with open("/Users/zhangjr/apps/LlmDemo/vibe-project/vela-worker/.cursor/debug-75b2b5.log", "a") as _f:
            _f.write(_json.dumps({
                "sessionId": "75b2b5",
                "runId": run_id,
                "hypothesisId": hypothesis_id,
                "location": location,
                "message": message,
                "data": data or {},
                "timestamp": int(_time.time() * 1000),
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion


def _remount_entry_sub_agents(
    entry_id: str,
    duty_agent_pairs: List[tuple],
    *,
    reception_agent_id: str = "",
    duties: List[Duty] = None,
):
    """Replace COMPOSITE sub-agents: reception first, then duty agents."""
    try:
        composition = vela_agent_client.get_composition(entry_id)
        for sub in composition.get("sub_agents") or []:
            child_id = sub.get("child_agent_id")
            if child_id:
                try:
                    vela_agent_client.remove_sub_agent(entry_id, child_id)
                except Exception:
                    pass
    except Exception:
        pass

    if reception_agent_id:
        try:
            vela_agent_client.republish_agent(reception_agent_id)
        except Exception:
            pass
        vela_agent_client.add_sub_agent(
            entry_id,
            reception_agent_id,
            role_name="基础接待",
            role_description=_reception_role_description(duties or []),
            task_keywords=list(RECEPTION_TASK_KEYWORDS),
        )

    for duty, child_agent_id in duty_agent_pairs:
        try:
            vela_agent_client.republish_agent(child_agent_id)
        except Exception:
            pass
        vela_agent_client.add_sub_agent(
            entry_id,
            child_agent_id,
            role_name=duty.name,
            role_description=duty.description or "",
            task_keywords=_duty_task_keywords(duty),
        )


def _update_existing_entry_agent(
    entry_id: str,
    *,
    worker: DigitalWorker,
    role: DigitalRole,
    duties: List[Duty],
    duty_agent_pairs: List[tuple],
    entry_name: str,
    system_prompt: str,
    reception_agent_id: str,
) -> str:
    """Reuse existing COMPOSITE entry: update prompt, remount subs, ensure published."""
    # If previously deprecated during a failed rebuild, bring it back
    try:
        info = vela_agent_client.get_agent(entry_id)
        status = (info.get("status") or "").upper()
    except Exception as e:
        raise VelaAgentError(f"load entry failed: {e}")

    if status == "DEPRECATED":
        vela_agent_client.republish_agent(entry_id)

    vela_agent_client.update_agent(entry_id, {
        "name": entry_name[:120],
        "description": f"数字员工 {worker.name}（{worker.employee_no}）入口 COMPOSITE Agent",
        "system_prompt": system_prompt,
        "dept_id": worker.dept_id or "",
        "change_summary": "sync entry duties",
    })
    if SHARED_KB_IDS:
        try:
            vela_agent_client.bind_knowledge_bases(entry_id, list(SHARED_KB_IDS))
        except Exception:
            pass
    try:
        vela_agent_client.set_memory_enabled(entry_id, True)
    except Exception:
        pass

    vela_agent_client.update_coordinator_config(entry_id, {
        "dispatch_strategy": "llm",
        "result_integration": "coordinator",
        "max_dispatch_rounds": 5,
        "hitl_before_delivery": False,
        "total_token_budget": 500000,
        "max_a2a_calls": 20,
    })
    _remount_entry_sub_agents(
        entry_id,
        duty_agent_pairs,
        reception_agent_id=reception_agent_id,
        duties=duties,
    )

    vr = vela_agent_client.validate_agent(entry_id)
    ok = vr.get("valid", vr.get("passed", True))
    if not ok:
        raise HTTPException(status_code=400, detail=f"入口 Agent 校验失败: {vr.get('errors') or vr}")

    # publish if draft; republish already handled DEPRECATED
    try:
        if status in ("DRAFT", ""):
            vela_agent_client.publish_agent(entry_id, f"数字员工 {worker.name} 入口 Agent 同步")
        elif status == "PUBLISHED":
            pass
        else:
            try:
                vela_agent_client.publish_agent(entry_id, f"数字员工 {worker.name} 入口 Agent 同步")
            except Exception:
                try:
                    vela_agent_client.republish_agent(entry_id)
                except Exception:
                    pass
    except Exception:
        pass

    return entry_id


def _ensure_entry_agent(
    db: Session,
    worker: DigitalWorker,
    role: DigitalRole,
    duties: List[Duty],
    *,
    duty_agent_pairs: List[tuple],
) -> str:
    """Create or rebuild COMPOSITE entry agent and mount reception + duty sub-agents."""
    dept_name = ""
    if worker.dept_id:
        dept = db.query(Department).filter(Department.dept_id == worker.dept_id).first()
        dept_name = dept.name if dept else ""

    model_service_id = _resolve_entry_model_service_id(role)
    if not model_service_id:
        raise HTTPException(status_code=400, detail="无可用模型服务创建入口 Agent")

    entry_name = f"DW-{worker.employee_no}-{worker.name}-入口"
    system_prompt = _build_entry_system_prompt(worker.name, worker.employee_no, dept_name, role, duties)
    old_entry_id = (worker.entry_agent_id or "").strip()

    reception_id = _ensure_reception_agent(
        worker, role, duties, dept_name=dept_name, model_service_id=model_service_id,
    )
    worker.reception_agent_id = reception_id

    _dbg_entry("A", "worker_service.py:_ensure_entry_agent:start", "ensure entry start", {
        "employee_no": worker.employee_no,
        "old_entry_id": old_entry_id,
        "entry_name": entry_name[:120],
        "reception_agent_id": reception_id,
        "duty_names": [d.name for d in duties],
        "duty_ids": [d.duty_id for d in duties],
    })

    # Prefer in-place update to avoid global name unique 409 after deprecate
    if old_entry_id:
        try:
            entry_id = _update_existing_entry_agent(
                old_entry_id,
                worker=worker,
                role=role,
                duties=duties,
                duty_agent_pairs=duty_agent_pairs,
                entry_name=entry_name,
                system_prompt=system_prompt,
                reception_agent_id=reception_id,
            )
            worker.entry_agent_id = entry_id
            _dbg_entry("A", "worker_service.py:_ensure_entry_agent:inplace_ok", "in-place entry sync ok", {
                "entry_id": entry_id,
                "reception_agent_id": reception_id,
                "duty_names": [d.name for d in duties],
            })
            return entry_id
        except HTTPException:
            raise
        except Exception as e:
            _dbg_entry("A", "worker_service.py:_ensure_entry_agent:inplace_fail", "in-place failed, fallback create", {
                "old_entry_id": old_entry_id,
                "error": str(e),
            })
            try:
                vela_agent_client.deprecate_agent(old_entry_id)
            except Exception:
                pass
            try:
                vela_agent_client.update_agent(old_entry_id, {
                    "name": f"{entry_name[:90]}-old-{old_entry_id[:8]}",
                    "change_summary": "release name for entry rebuild",
                })
            except Exception as rename_err:
                _dbg_entry("A", "worker_service.py:_ensure_entry_agent:rename_fail", "rename old entry failed", {
                    "error": str(rename_err),
                })

    try:
        created = vela_agent_client.create_agent({
            "name": entry_name[:120],
            "description": f"数字员工 {worker.name}（{worker.employee_no}）入口 COMPOSITE Agent",
            "agent_type": "COMPOSITE",
            "model_service_id": model_service_id,
            "system_prompt": system_prompt,
            "dept_id": worker.dept_id or "",
            "autonomy_level": (role.governance or {}).get("autonomy_level", "L2"),
            "knowledge_base_ids": list(SHARED_KB_IDS),
            "tags": ["digital-worker", "entry", worker.employee_no, getattr(role, "code", None) or role.role_id or ""],
            "composition_config": {
                "dispatch_strategy": "llm",
                "result_integration": "coordinator",
                "max_dispatch_rounds": 5,
                "hitl_before_delivery": False,
                "total_token_budget": 500000,
            },
        })
        entry_id = created["agent_id"]
        _dbg_entry("A", "worker_service.py:_ensure_entry_agent:create_ok", "create entry succeeded", {
            "entry_id": entry_id,
            "entry_name": entry_name[:120],
            "reception_agent_id": reception_id,
            "duty_names": [d.name for d in duties],
        })

        if SHARED_KB_IDS:
            vela_agent_client.bind_knowledge_bases(entry_id, list(SHARED_KB_IDS))
        vela_agent_client.set_memory_enabled(entry_id, True)

        vela_agent_client.update_coordinator_config(entry_id, {
            "dispatch_strategy": "llm",
            "result_integration": "coordinator",
            "max_dispatch_rounds": 5,
            "hitl_before_delivery": False,
            "total_token_budget": 500000,
            "max_a2a_calls": 20,
        })
        _remount_entry_sub_agents(
            entry_id,
            duty_agent_pairs,
            reception_agent_id=reception_id,
            duties=duties,
        )

        vr = vela_agent_client.validate_agent(entry_id)
        ok = vr.get("valid", vr.get("passed", True))
        if not ok:
            raise HTTPException(status_code=400, detail=f"入口 Agent 校验失败: {vr.get('errors') or vr}")
        vela_agent_client.publish_agent(entry_id, f"数字员工 {worker.name} 入口 Agent")
        worker.entry_agent_id = entry_id
        return entry_id
    except HTTPException:
        raise
    except VelaAgentError as e:
        _dbg_entry("A", "worker_service.py:_ensure_entry_agent:create_fail", "create entry failed", {
            "entry_name": entry_name[:120],
            "old_entry_id": old_entry_id,
            "status_code": getattr(e, "status_code", None),
            "error": str(e),
            "detail": getattr(e, "detail", None),
        })
        raise HTTPException(status_code=502, detail=f"创建入口 COMPOSITE Agent 失败: {e}")


def _sync_entry_after_duty_change(db: Session, worker: DigitalWorker):
    """Rebuild entry COMPOSITE composition to match current active duties."""
    # Session uses autoflush=False; persist duty status changes before querying actives
    db.flush()
    role = db.query(DigitalRole).filter(DigitalRole.role_id == worker.role_id).first()
    if not role:
        return
    pairs = []
    duties = []
    for wda, duty in list_active_worker_duties(db, worker.worker_id):
        if not wda.agent_id:
            continue
        pairs.append((duty, wda.agent_id))
        duties.append(duty)
    _dbg_entry("E", "worker_service.py:_sync_entry_after_duty_change", "active duties after flush", {
        "employee_no": worker.employee_no,
        "duty_names": [d.name for d in duties],
        "duty_ids": [d.duty_id for d in duties],
        "entry_agent_id": worker.entry_agent_id or "",
        "reception_agent_id": worker.reception_agent_id or "",
    })
    # Even with zero duties, keep entry COMPOSITE + reception for chitchat / OOS refusal
    _ensure_entry_agent(db, worker, role, duties, duty_agent_pairs=pairs)


def repair_worker_entry(db: Session, worker_id: str, actor_id: str = "system") -> DigitalWorker:
    """Rebuild entry COMPOSITE for an existing worker (migration / fix)."""
    worker = db.query(DigitalWorker).filter(DigitalWorker.worker_id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="数字员工不存在")
    if worker.status == WorkerStatus.OFFBOARDED:
        raise HTTPException(status_code=400, detail="已离职员工不可修复编排")
    _sync_entry_after_duty_change(db, worker)
    worker.spec_revision = (worker.spec_revision or 1) + 1
    worker.updated_at = now_utc()
    save_spec_snapshot(db, worker, changed_by=actor_id)
    db.add(WorkerAuditLog(
        worker_id=worker_id, actor_type="HUMAN", actor_id=actor_id,
        action="REPAIR_ENTRY", detail={"entry_agent_id": worker.entry_agent_id},
    ))
    db.commit()
    db.refresh(worker)
    return worker


def _worker_duties_payload(db: Session, worker: DigitalWorker) -> list:
    items = []
    for wda, duty in list_active_worker_duties(db, worker.worker_id):
        items.append({
            "duty_id": duty.duty_id,
            "duty_name": duty.name,
            "agent_id": wda.agent_id or "",
            "source": wda.source.value if hasattr(wda.source, "value") else wda.source,
            "is_primary": bool(wda.is_primary),
            "status": wda.status.value if hasattr(wda.status, "value") else wda.status,
            "task_types": duty.task_types or [],
            "keywords": duty.keywords or [],
        })
    return items


def _worker_response_fields(db: Session, worker: DigitalWorker) -> dict:
    role = db.query(DigitalRole).filter(DigitalRole.role_id == worker.role_id).first()
    dept = db.query(Department).filter(Department.dept_id == worker.dept_id).first() if worker.dept_id else None
    duties = _worker_duties_payload(db, worker)
    primary = next((d for d in duties if d.get("is_primary")), duties[0] if duties else None)
    return {
        "worker_id": worker.worker_id,
        "employee_no": worker.employee_no,
        "name": worker.name,
        "avatar": worker.avatar or "",
        "role_id": worker.role_id,
        "role_version": worker.role_version,
        "role_name": role.name if role else "",
        "dept_id": worker.dept_id,
        "dept_name": dept.name if dept else "",
        "entry_agent_id": worker.entry_agent_id or "",
        "reception_agent_id": worker.reception_agent_id or "",
        "duties": duties,
        "duty_count": len(duties),
        "primary_agent_id": (primary or {}).get("agent_id", "") or (worker.entry_agent_id or ""),
        "permission_overrides": worker.permission_overrides or {},
        "governance_overrides": worker.governance_overrides or {},
        "escalation_contact": worker.escalation_contact or {},
        "duty_scope_override": worker.duty_scope_override or [],
        "spec_revision": worker.spec_revision,
        "status": worker.status.value if hasattr(worker.status, "value") else worker.status,
        "remark": worker.remark or "",
        "onboard_at": worker.onboard_at,
        "created_at": worker.created_at,
    }



def save_spec_snapshot(db: Session, worker: DigitalWorker, changed_by: str = "system"):
    role = db.query(DigitalRole).filter(DigitalRole.role_id == worker.role_id).first()
    spec = build_worker_spec(db, worker, role)
    db.add(WorkerSpecHistory(
        worker_id=worker.worker_id,
        spec_revision=worker.spec_revision,
        spec=spec,
        changed_by=changed_by,
    ))


def onboard_worker(
    db: Session,
    *,
    name: str,
    role_id: str,
    dept_id: Optional[str] = None,
    avatar: str = "",
    escalation_contact: dict = None,
    remark: str = "",
    actor_id: str = "system",
) -> DigitalWorker:
    role = db.query(DigitalRole).filter(DigitalRole.role_id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    if role.status.value != "ACTIVE" if hasattr(role.status, "value") else role.status != "ACTIVE":
        raise HTTPException(status_code=400, detail="角色已停用")

    duty_ids = role.duty_ids or []
    if not duty_ids:
        raise HTTPException(status_code=400, detail="角色未关联任何职责，请先在角色中配置职责")

    duties: List[Duty] = []
    for did in duty_ids:
        duty = db.query(Duty).filter(Duty.duty_id == did).first()
        if not duty:
            raise HTTPException(status_code=400, detail=f"角色关联的职责不存在: {did}")
        if (duty.status.value if hasattr(duty.status, "value") else duty.status) != "ACTIVE":
            raise HTTPException(status_code=400, detail=f"职责已停用: {duty.name}")
        duties.append(duty)

    dept_name = ""
    if dept_id:
        dept = db.query(Department).filter(Department.dept_id == dept_id).first()
        if not dept:
            raise HTTPException(status_code=404, detail="部门不存在")
        dept_name = dept.name

    employee_no = allocate_employee_no(db)
    gov = role.governance or {}

    worker = DigitalWorker(
        worker_id=gen_uuid(),
        employee_no=employee_no,
        name=name,
        avatar=avatar or "",
        role_id=role_id,
        role_version=role.version,
        dept_id=dept_id,
        escalation_contact=escalation_contact or gov.get("escalation_contact") or {},
        remark=remark,
        status=WorkerStatus.ON_DUTY,
        spec_revision=1,
        onboard_at=now_utc(),
    )
    db.add(worker)
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
            worker_id=worker.worker_id,
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
    save_spec_snapshot(db, worker, changed_by=actor_id)
    db.add(WorkerAuditLog(
        worker_id=worker.worker_id,
        actor_type="HUMAN",
        actor_id=actor_id,
        action="ONBOARD",
        detail={
            "employee_no": employee_no,
            "duty_ids": duty_ids,
            "agent_ids": agent_ids,
            "entry_agent_id": entry_agent_id,
        },
    ))
    db.commit()
    db.refresh(worker)
    return worker


def add_worker_duty(
    db: Session,
    worker_id: str,
    duty_id: str,
    *,
    is_primary: bool = False,
    actor_id: str = "system",
) -> DigitalWorker:
    worker = db.query(DigitalWorker).filter(DigitalWorker.worker_id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="数字员工不存在")
    if worker.status == WorkerStatus.OFFBOARDED:
        raise HTTPException(status_code=400, detail="已离职员工不可追加职责")

    duty = db.query(Duty).filter(Duty.duty_id == duty_id).first()
    if not duty:
        raise HTTPException(status_code=404, detail="职责不存在")
    if (duty.status.value if hasattr(duty.status, "value") else duty.status) != "ACTIVE":
        raise HTTPException(status_code=400, detail="职责已停用")

    existing = db.query(WorkerDutyAgent).filter(
        WorkerDutyAgent.worker_id == worker_id,
        WorkerDutyAgent.duty_id == duty_id,
    ).first()
    if existing and existing.status == WorkerDutyStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="该职责已配置")

    role = db.query(DigitalRole).filter(DigitalRole.role_id == worker.role_id).first()
    dept_name = ""
    if worker.dept_id:
        dept = db.query(Department).filter(Department.dept_id == worker.dept_id).first()
        dept_name = dept.name if dept else ""

    agent_id = _create_and_publish_duty_agent(
        employee_no=worker.employee_no,
        worker_name=worker.name,
        dept_id=worker.dept_id,
        dept_name=dept_name,
        duty=duty,
        role=role,
        worker_overrides=worker.permission_overrides or {},
        worker_gov_overrides=worker.governance_overrides or {},
    )

    if is_primary:
        for wda, _ in list_active_worker_duties(db, worker_id):
            wda.is_primary = False

    if existing:
        existing.agent_id = agent_id
        existing.source = WorkerDutySource.EXTRA
        existing.status = WorkerDutyStatus.ACTIVE
        existing.is_primary = is_primary
        existing.updated_at = now_utc()
    else:
        # if no active duties yet, force primary
        actives = list_active_worker_duties(db, worker_id)
        force_primary = is_primary or not actives
        if force_primary:
            for wda, _ in actives:
                wda.is_primary = False
        db.add(WorkerDutyAgent(
            worker_id=worker_id,
            duty_id=duty_id,
            agent_id=agent_id,
            source=WorkerDutySource.EXTRA,
            is_primary=force_primary,
            status=WorkerDutyStatus.ACTIVE,
        ))

    worker.spec_revision = (worker.spec_revision or 1) + 1
    worker.updated_at = now_utc()
    _sync_entry_after_duty_change(db, worker)
    save_spec_snapshot(db, worker, changed_by=actor_id)
    db.add(WorkerAuditLog(
        worker_id=worker_id, actor_type="HUMAN", actor_id=actor_id,
        action="ADD_DUTY", detail={"duty_id": duty_id, "agent_id": agent_id, "entry_agent_id": worker.entry_agent_id},
    ))
    db.commit()
    db.refresh(worker)
    return worker


def remove_worker_duty(
    db: Session,
    worker_id: str,
    duty_id: str,
    *,
    actor_id: str = "system",
) -> DigitalWorker:
    worker = db.query(DigitalWorker).filter(DigitalWorker.worker_id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="数字员工不存在")
    wda = db.query(WorkerDutyAgent).filter(
        WorkerDutyAgent.worker_id == worker_id,
        WorkerDutyAgent.duty_id == duty_id,
        WorkerDutyAgent.status == WorkerDutyStatus.ACTIVE,
    ).first()
    if not wda:
        raise HTTPException(status_code=404, detail="未找到该职责配置")

    was_primary = bool(wda.is_primary)
    if wda.agent_id:
        try:
            vela_agent_client.deprecate_agent(wda.agent_id)
        except Exception:
            pass
    wda.status = WorkerDutyStatus.REMOVED
    wda.is_primary = False
    wda.updated_at = now_utc()

    if was_primary:
        remaining = list_active_worker_duties(db, worker_id)
        if remaining:
            remaining[0][0].is_primary = True

    worker.spec_revision = (worker.spec_revision or 1) + 1
    worker.updated_at = now_utc()
    # #region agent log
    try:
        import json as _json, time as _time
        with open("/Users/zhangjr/apps/LlmDemo/vibe-project/vela-worker/.cursor/debug-75b2b5.log", "a") as _f:
            _f.write(_json.dumps({
                "sessionId": "75b2b5",
                "runId": "pre-fix",
                "hypothesisId": "C",
                "location": "worker_service.py:remove_worker_duty",
                "message": "before sync entry after remove duty",
                "data": {
                    "worker_id": worker_id,
                    "duty_id": duty_id,
                    "entry_agent_id": worker.entry_agent_id or "",
                    "employee_no": worker.employee_no,
                },
                "timestamp": int(_time.time() * 1000),
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion
    _sync_entry_after_duty_change(db, worker)
    save_spec_snapshot(db, worker, changed_by=actor_id)
    db.add(WorkerAuditLog(
        worker_id=worker_id, actor_type="HUMAN", actor_id=actor_id,
        action="REMOVE_DUTY", detail={"duty_id": duty_id, "entry_agent_id": worker.entry_agent_id},
    ))
    db.commit()
    db.refresh(worker)
    return worker


def apply_permission_overrides(
    db: Session,
    worker_id: str,
    *,
    tool_overrides: list = None,
    kb_overrides: dict = None,
    governance_overrides: dict = None,
    duty_scope_override: list = None,
    actor_id: str = "system",
    is_platform_admin: bool = False,
) -> DigitalWorker:
    worker = db.query(DigitalWorker).filter(DigitalWorker.worker_id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="数字员工不存在")
    role = db.query(DigitalRole).filter(DigitalRole.role_id == worker.role_id).first()

    existing = worker.permission_overrides or {}
    new_overrides = dict(existing)
    if tool_overrides is not None:
        if any(ov.get("permission") == "allowed" for ov in tool_overrides) and not is_platform_admin:
            # widen check simplified: platform admin for allowing previously denied
            pass
        new_overrides["tool_overrides"] = tool_overrides
    if kb_overrides is not None:
        if kb_overrides.get("add") and not is_platform_admin:
            raise HTTPException(status_code=403, detail="新增知识库需要平台管理员")
        new_overrides["kb_overrides"] = kb_overrides
    if governance_overrides is not None:
        if governance_overrides.get("autonomy_level"):
            levels = {"L1": 1, "L2": 2, "L3": 3, "L4": 4}
            old = (role.governance or {}).get("autonomy_level", "L2") if role else "L2"
            new = governance_overrides["autonomy_level"]
            if levels.get(new, 2) > levels.get(old, 2) and not is_platform_admin:
                raise HTTPException(status_code=403, detail="提升自治级别需要平台管理员")
        worker.governance_overrides = {
            **(worker.governance_overrides or {}),
            **governance_overrides,
        }
        new_overrides["governance_overrides"] = worker.governance_overrides

    worker.permission_overrides = new_overrides
    if duty_scope_override is not None:
        worker.duty_scope_override = duty_scope_override

    # replay bindings on all duty agents
    for wda, duty in list_active_worker_duties(db, worker.worker_id):
        if not wda.agent_id:
            continue
        try:
            bindings = effective_tool_bindings_for_duty(duty, worker)
            vela_agent_client.bind_tools(wda.agent_id, bindings)
            kb_ids = effective_kb_ids_for_duty(duty, worker, SHARED_KB_IDS)
            vela_agent_client.bind_knowledge_bases(wda.agent_id, kb_ids)
            gov = {**(duty.governance or {}), **(role.governance if role else {}), **(worker.governance_overrides or {})}
            update = {}
            if gov.get("autonomy_level"):
                update["autonomy_level"] = gov["autonomy_level"]
            if gov.get("token_budget_per_task") or gov.get("token_budget"):
                update["token_budget"] = gov.get("token_budget_per_task") or gov.get("token_budget")
            if update:
                update["change_summary"] = "permission override"
                vela_agent_client.update_agent(wda.agent_id, update)
        except VelaAgentError as e:
            raise HTTPException(status_code=502, detail=f"同步权限失败（{duty.name}）: {e}")

    worker.spec_revision = (worker.spec_revision or 1) + 1
    worker.updated_at = now_utc()
    save_spec_snapshot(db, worker, changed_by=actor_id)
    db.add(WorkerAuditLog(
        worker_id=worker.worker_id,
        actor_type="HUMAN",
        actor_id=actor_id,
        action="PERMISSION_OVERRIDE",
        detail=new_overrides,
    ))
    db.commit()
    db.refresh(worker)
    return worker


def set_worker_status(db: Session, worker_id: str, status: str, actor_id: str = "system") -> DigitalWorker:
    worker = db.query(DigitalWorker).filter(DigitalWorker.worker_id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="数字员工不存在")

    wdas = db.query(WorkerDutyAgent).filter(
        WorkerDutyAgent.worker_id == worker_id,
        WorkerDutyAgent.status == WorkerDutyStatus.ACTIVE,
    ).all()

    def _all_agent_ids():
        ids = [wda.agent_id for wda in wdas if wda.agent_id]
        if worker.entry_agent_id:
            ids.append(worker.entry_agent_id)
        if worker.reception_agent_id:
            ids.append(worker.reception_agent_id)
        return ids

    if status == "SUSPENDED":
        worker.status = WorkerStatus.SUSPENDED
        for aid in _all_agent_ids():
            try:
                vela_agent_client.deprecate_agent(aid)
            except Exception:
                pass
    elif status == "ON_DUTY":
        worker.status = WorkerStatus.ON_DUTY
        # republish duty agents first, then rebuild/republish entry COMPOSITE
        for wda in wdas:
            if wda.agent_id:
                try:
                    vela_agent_client.republish_agent(wda.agent_id)
                except Exception:
                    pass
        try:
            _sync_entry_after_duty_change(db, worker)
        except Exception:
            if worker.entry_agent_id:
                try:
                    vela_agent_client.republish_agent(worker.entry_agent_id)
                except Exception:
                    pass
            if worker.reception_agent_id:
                try:
                    vela_agent_client.republish_agent(worker.reception_agent_id)
                except Exception:
                    pass
    elif status == "OFFBOARDED":
        worker.status = WorkerStatus.OFFBOARDED
        worker.offboard_at = now_utc()
        for aid in _all_agent_ids():
            try:
                vela_agent_client.deprecate_agent(aid)
            except Exception:
                pass
    else:
        raise HTTPException(status_code=400, detail="无效状态")
    db.add(WorkerAuditLog(
        worker_id=worker.worker_id, actor_type="HUMAN", actor_id=actor_id,
        action="STATUS_CHANGE", detail={
            "status": status,
            "entry_agent_id": worker.entry_agent_id,
            "reception_agent_id": worker.reception_agent_id,
        },
    ))
    db.commit()
    db.refresh(worker)
    return worker
