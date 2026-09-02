"""HITL bridge: approve/reject from IM cards, info reply injection."""
from typing import Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session
from models import WorkTask, Message, TaskStatus, DigitalWorker, MemberType, gen_uuid, now_utc
from services.vela_agent_client import vela_agent_client, VelaAgentError
from services.im_service import push_message
from sqlalchemy.orm.attributes import flag_modified


def classify_approval_kind(tool_name: str, tool_args: Optional[dict]) -> str:
    """Map vela-agent approval to IM card kind."""
    tool_args = tool_args or {}
    flow_kind = tool_args.get("flow_kind") or ""
    name = tool_name or ""
    if name == "cu_login_otp" or flow_kind == "otp_wait":
        return "otp"
    if name == "cu_skill_params" or flow_kind == "skill_params":
        return "skill_params"
    if name == "__delivery__":
        return "delivery"
    if name == "__workflow_hitl__":
        return "workflow"
    return "tool"


def build_approval_card_content(task_id: str, session_id: str, approval: dict) -> dict:
    tool_name = approval.get("tool_name") or ""
    tool_args = approval.get("tool_args") or {}
    kind = classify_approval_kind(tool_name, tool_args)
    texts = {
        "otp": "需要输入登录验证码以继续 ScreenPilot 操作",
        "skill_params": "需要补充技能参数以继续执行",
        "delivery": "需要审批多 Agent 交付结果",
        "workflow": "需要审批工作流节点",
        "tool": f"需要审批：工具 {tool_name}",
    }
    missing_params = list(tool_args.get("missing_params") or [])
    if kind == "skill_params" and not missing_params:
        # fallback: infer from param schema if present
        schema = tool_args.get("param_schema") or tool_args.get("params") or {}
        if isinstance(schema, dict):
            missing_params = list(schema.keys())
    return {
        "task_id": task_id,
        "approval_id": approval.get("approval_id"),
        "session_id": session_id,
        "tool_name": tool_name,
        "tool_args": tool_args,
        "approval_kind": kind,
        "missing_params": missing_params,
        "status": "PENDING",
        "text": texts.get(kind, texts["tool"]),
    }


async def post_approval_card(
    db: Session,
    *,
    conv_id: str,
    worker: DigitalWorker,
    task_id: str,
    session_id: str,
    approval: dict,
) -> Message:
    content = build_approval_card_content(task_id, session_id, approval)
    msg = Message(
        msg_id=gen_uuid(),
        conv_id=conv_id,
        sender_type=MemberType.WORKER,
        sender_id=worker.worker_id,
        msg_type="approval_card",
        content=content,
        ref_task_id=task_id,
        ref_approval_id=approval.get("approval_id"),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    await push_message(db, msg)
    return msg


async def _follow_up_after_approval(
    db: Session,
    *,
    msg: Message,
    result: dict,
    approved: bool,
):
    """Handle v0.95 approve response: session_status and chained pending approvals."""
    if not msg.ref_task_id:
        return

    task = db.query(WorkTask).filter(WorkTask.task_id == msg.ref_task_id).first()
    if not task:
        return

    session_id = (msg.content or {}).get("session_id") or task.agent_session_id
    session_status = (result or {}).get("session_status")
    pending_aid = (result or {}).get("pending_approval_id")

    if approved:
        if session_status == "RUNNING":
            task.status = TaskStatus.RUNNING
            task.status_detail = "审批通过，继续执行"
        elif session_status == "HITL_WAIT" or pending_aid:
            task.status = TaskStatus.NEED_HUMAN
            task.status_detail = "仍有待处理审批"
        elif task.status == TaskStatus.NEED_HUMAN:
            task.status = TaskStatus.RUNNING
            task.status_detail = "审批通过，继续执行"
        db.commit()

        if pending_aid and task.conv_id and session_id:
            worker = db.query(DigitalWorker).filter(DigitalWorker.worker_id == task.worker_id).first()
            if not worker:
                return
            try:
                approvals = await vela_agent_client.alist_pending_approvals(session_id)
            except VelaAgentError:
                approvals = []
            target = next((a for a in approvals if a.get("approval_id") == pending_aid), None)
            if not target and isinstance(result.get("preview_payload"), dict):
                target = {
                    "approval_id": pending_aid,
                    "tool_name": result.get("tool_name") or "cu_skill_params",
                    "tool_args": result.get("preview_payload") or {},
                }
            if target:
                existing = db.query(Message).filter(
                    Message.conv_id == task.conv_id,
                    Message.ref_approval_id == pending_aid,
                    Message.msg_type == "approval_card",
                ).first()
                if not existing:
                    await post_approval_card(
                        db,
                        conv_id=task.conv_id,
                        worker=worker,
                        task_id=task.task_id,
                        session_id=session_id,
                        approval=target,
                    )


async def handle_approval(
    db: Session,
    *,
    msg_id: str,
    approved: bool,
    reviewer: str,
    comment: str = "",
    otp_code: Optional[str] = None,
    param_values: Optional[dict] = None,
) -> dict:
    msg = db.query(Message).filter(Message.msg_id == msg_id).first()
    if not msg or msg.msg_type != "approval_card":
        raise HTTPException(status_code=404, detail="审批卡片不存在")
    content = dict(msg.content or {})
    if content.get("status") and content["status"] != "PENDING":
        raise HTTPException(status_code=400, detail="该审批已处理")

    session_id = content.get("session_id")
    approval_id = content.get("approval_id") or msg.ref_approval_id
    if not session_id or not approval_id:
        raise HTTPException(status_code=400, detail="审批卡片缺少 session/approval")

    kind = content.get("approval_kind") or classify_approval_kind(
        content.get("tool_name", ""), content.get("tool_args"),
    )
    if approved and kind == "otp" and not (otp_code or comment):
        raise HTTPException(status_code=400, detail="请提供验证码")
    if approved and kind == "skill_params":
        pv = param_values or {}
        missing = content.get("missing_params") or []
        still = [k for k in missing if not str(pv.get(k) or "").strip()]
        if still:
            raise HTTPException(status_code=400, detail=f"请填写参数: {', '.join(still)}")

    try:
        if approved:
            result = vela_agent_client.approve(
                session_id,
                approval_id,
                reviewer=reviewer,
                comment=comment,
                otp_code=otp_code,
                param_values=param_values,
            )
        else:
            result = vela_agent_client.reject(
                session_id,
                approval_id,
                reviewer=reviewer,
                comment=comment,
            )
    except VelaAgentError as e:
        raise HTTPException(status_code=502, detail=str(e))

    content["status"] = "APPROVED" if approved else "REJECTED"
    content["reviewer"] = reviewer
    content["comment"] = comment
    content["reviewed_at"] = now_utc().isoformat()
    msg.content = content
    flag_modified(msg, "content")
    db.commit()
    await push_message(db, msg)

    await _follow_up_after_approval(db, msg=msg, result=result, approved=approved)

    return {"ok": True, "result": result}


async def handle_info_reply(
    db: Session,
    *,
    task_id: str,
    message: str,
    user_id: str,
) -> dict:
    task = db.query(WorkTask).filter(WorkTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not task.agent_session_id:
        raise HTTPException(status_code=400, detail="任务无 Agent 会话")
    try:
        await vela_agent_client.achat_async(
            task.agent_session_id,
            f"【人工补充信息 · 来自 {user_id}】\n{message}",
        )
    except VelaAgentError as e:
        raise HTTPException(status_code=502, detail=str(e))

    if task.status == TaskStatus.NEED_HUMAN:
        task.status = TaskStatus.RUNNING
        task.status_detail = "已收到补充信息"
        db.commit()
    return {"ok": True}
