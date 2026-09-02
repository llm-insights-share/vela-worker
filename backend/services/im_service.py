"""IM conversations, messages, routing to digital workers."""
import re
from typing import List, Optional, Tuple
from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session
from models import (
    Conversation, ConversationMember, Message, DigitalWorker, HumanUser,
    WorkerImSession, MemberType, ConvType, WorkerStatus, gen_uuid, now_utc,
)
from services.vela_agent_client import vela_agent_client, VelaAgentError
from services.spec_builder import build_worker_spec
from services.ws_hub import ws_manager


def _member_display(db: Session, member_type: str, member_id: str) -> dict:
    if member_type == "HUMAN" or member_type == MemberType.HUMAN:
        u = db.query(HumanUser).filter(HumanUser.user_id == member_id).first()
        return {
            "member_type": "HUMAN",
            "member_id": member_id,
            "name": u.name if u else member_id,
            "avatar": u.avatar if u else "",
        }
    w = db.query(DigitalWorker).filter(DigitalWorker.worker_id == member_id).first()
    return {
        "member_type": "WORKER",
        "member_id": member_id,
        "name": w.name if w else member_id,
        "avatar": w.avatar if w else "",
        "employee_no": w.employee_no if w else "",
        "status": w.status.value if w and hasattr(w.status, "value") else (w.status if w else ""),
    }


def list_human_member_ids(db: Session, conv_id: str) -> List[str]:
    rows = db.query(ConversationMember).filter(
        ConversationMember.conv_id == conv_id,
        ConversationMember.member_type == MemberType.HUMAN,
    ).all()
    return [r.member_id for r in rows]


def message_to_dict(db: Session, msg: Message) -> dict:
    disp = _member_display(db, msg.sender_type.value if hasattr(msg.sender_type, "value") else msg.sender_type, msg.sender_id)
    return {
        "msg_id": msg.msg_id,
        "conv_id": msg.conv_id,
        "sender_type": msg.sender_type.value if hasattr(msg.sender_type, "value") else msg.sender_type,
        "sender_id": msg.sender_id,
        "sender_name": disp.get("name", ""),
        "msg_type": msg.msg_type,
        "content": msg.content or {},
        "ref_task_id": msg.ref_task_id,
        "ref_approval_id": msg.ref_approval_id,
        "created_at": msg.created_at,
    }


async def push_message(db: Session, msg: Message):
    event = {"type": "message", "data": message_to_dict(db, msg)}
    await ws_manager.broadcast_to_users(list_human_member_ids(db, msg.conv_id), event)


def create_conversation(
    db: Session,
    *,
    conv_type: str,
    name: str,
    owner_id: str,
    members: List[dict],
) -> Conversation:
    ctype = ConvType.GROUP if conv_type == "GROUP" else ConvType.DIRECT
    # ensure owner in members
    member_keys = {(m["member_type"], m["member_id"]) for m in members}
    if ("HUMAN", owner_id) not in member_keys:
        members = list(members) + [{"member_type": "HUMAN", "member_id": owner_id}]

    if ctype == ConvType.DIRECT:
        # find existing direct between same two parties
        if len(members) != 2:
            raise HTTPException(status_code=400, detail="单聊必须恰好两名成员")
        # skip dedup for simplicity in MVP or implement
        pass

    conv = Conversation(
        conv_id=gen_uuid(),
        type=ctype,
        name=name or ("群聊" if ctype == ConvType.GROUP else ""),
        owner_id=owner_id,
    )
    db.add(conv)
    db.flush()

    worker_members = []
    for m in members:
        mt = MemberType.WORKER if m["member_type"] == "WORKER" else MemberType.HUMAN
        # validate
        if mt == MemberType.HUMAN:
            if not db.query(HumanUser).filter(HumanUser.user_id == m["member_id"]).first():
                raise HTTPException(status_code=404, detail=f"用户不存在: {m['member_id']}")
        else:
            w = db.query(DigitalWorker).filter(DigitalWorker.worker_id == m["member_id"]).first()
            if not w:
                raise HTTPException(status_code=404, detail=f"数字员工不存在: {m['member_id']}")
            worker_members.append(w)
        db.add(ConversationMember(
            conv_id=conv.conv_id,
            member_type=mt,
            member_id=m["member_id"],
        ))

    # auto name for direct
    if ctype == ConvType.DIRECT and not name:
        names = []
        for m in members:
            d = _member_display(db, m["member_type"], m["member_id"])
            names.append(d["name"])
        conv.name = " & ".join(names)

    db.commit()
    db.refresh(conv)

    # send worker_spec_card for each worker
    for w in worker_members:
        spec = build_worker_spec(db, w)
        msg = Message(
            msg_id=gen_uuid(),
            conv_id=conv.conv_id,
            sender_type=MemberType.WORKER,
            sender_id=w.worker_id,
            msg_type="worker_spec_card",
            content={"text": f"你好，我是数字员工 {w.name}（{w.employee_no}）", "spec": spec},
        )
        db.add(msg)
    db.commit()
    return conv


def _unread_count(db: Session, conv_id: str, user_id: str) -> int:
    """Count messages after member's last_read that were not sent by this user."""
    if not user_id:
        return 0
    member = db.query(ConversationMember).filter(
        ConversationMember.conv_id == conv_id,
        ConversationMember.member_type == MemberType.HUMAN,
        ConversationMember.member_id == user_id,
    ).first()
    if not member:
        return 0
    q = db.query(Message).filter(Message.conv_id == conv_id)
    last_read_id = (member.last_read_msg_id or "").strip()
    if last_read_id:
        ref = db.query(Message).filter(Message.msg_id == last_read_id).first()
        if ref and ref.created_at:
            q = q.filter(Message.created_at > ref.created_at)
        else:
            # stale id — treat as unread from start
            pass
    # exclude self-sent messages
    q = q.filter(
        or_(
            Message.sender_type != MemberType.HUMAN,
            Message.sender_id != user_id,
        )
    )
    return q.count()


def conversation_to_dict(db: Session, conv: Conversation, user_id: str = None) -> dict:
    members = db.query(ConversationMember).filter(ConversationMember.conv_id == conv.conv_id).all()
    member_list = [_member_display(db, m.member_type, m.member_id) for m in members]
    last = (
        db.query(Message)
        .filter(Message.conv_id == conv.conv_id)
        .order_by(Message.created_at.desc())
        .first()
    )
    return {
        "conv_id": conv.conv_id,
        "type": conv.type.value if hasattr(conv.type, "value") else conv.type,
        "name": conv.name,
        "avatar": conv.avatar or "",
        "owner_id": conv.owner_id,
        "members": member_list,
        "last_message": message_to_dict(db, last) if last else None,
        "unread_count": _unread_count(db, conv.conv_id, user_id) if user_id else 0,
        "created_at": conv.created_at,
    }


def mark_conversation_read(db: Session, conv_id: str, user_id: str) -> dict:
    """Mark conversation as read for a human member up to the latest message."""
    member = db.query(ConversationMember).filter(
        ConversationMember.conv_id == conv_id,
        ConversationMember.member_type == MemberType.HUMAN,
        ConversationMember.member_id == user_id,
    ).first()
    if not member:
        raise HTTPException(status_code=403, detail="非会话成员")
    last = (
        db.query(Message)
        .filter(Message.conv_id == conv_id)
        .order_by(Message.created_at.desc())
        .first()
    )
    if last:
        member.last_read_msg_id = last.msg_id
        db.commit()
    conv = db.query(Conversation).filter(Conversation.conv_id == conv_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")
    return conversation_to_dict(db, conv, user_id=user_id)


def add_members(db: Session, conv_id: str, members: List[dict]) -> Conversation:
    conv = db.query(Conversation).filter(Conversation.conv_id == conv_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")
    for m in members:
        exists = db.query(ConversationMember).filter(
            ConversationMember.conv_id == conv_id,
            ConversationMember.member_type == (MemberType.WORKER if m["member_type"] == "WORKER" else MemberType.HUMAN),
            ConversationMember.member_id == m["member_id"],
        ).first()
        if exists:
            continue
        mt = MemberType.WORKER if m["member_type"] == "WORKER" else MemberType.HUMAN
        db.add(ConversationMember(conv_id=conv_id, member_type=mt, member_id=m["member_id"]))
        if mt == MemberType.WORKER:
            w = db.query(DigitalWorker).filter(DigitalWorker.worker_id == m["member_id"]).first()
            if w:
                spec = build_worker_spec(db, w)
                db.add(Message(
                    msg_id=gen_uuid(),
                    conv_id=conv_id,
                    sender_type=MemberType.WORKER,
                    sender_id=w.worker_id,
                    msg_type="worker_spec_card",
                    content={"text": f"{w.name} 已加入会话", "spec": spec},
                ))
    db.commit()
    return conv


def get_or_create_im_session(db: Session, conv_id: str, worker: DigitalWorker, agent_id: str, duty_id: str = None) -> str:
    """Bind IM session to worker entry COMPOSITE agent (one session per conv×worker)."""
    row = db.query(WorkerImSession).filter(
        WorkerImSession.conv_id == conv_id,
        WorkerImSession.worker_id == worker.worker_id,
        WorkerImSession.status == "ACTIVE",
    ).order_by(WorkerImSession.id.desc()).first()
    if row and row.agent_session_id:
        return row.agent_session_id
    if not agent_id:
        raise HTTPException(status_code=400, detail="数字员工未配置入口 Agent")
    try:
        sess = vela_agent_client.create_session(
            agent_id=agent_id,
            caller_type="WORKER_IM",
            caller_id=f"{worker.worker_id}:{conv_id}",
        )
    except VelaAgentError as e:
        raise HTTPException(status_code=502, detail=f"创建 Agent 会话失败: {e}")
    sid = sess["session_id"]
    if row:
        row.agent_session_id = sid
        row.duty_id = duty_id
        row.last_active_at = now_utc()
    else:
        db.add(WorkerImSession(
            conv_id=conv_id,
            worker_id=worker.worker_id,
            duty_id=duty_id,
            agent_session_id=sid,
            status="ACTIVE",
        ))
    db.commit()
    return sid


def parse_mentions(text: str, workers: List[DigitalWorker]) -> List[DigitalWorker]:
    mentioned = []
    for w in workers:
        if f"@{w.name}" in text or f"@{w.employee_no}" in text:
            mentioned.append(w)
    return mentioned


def _recent_conversation_context(
    db: Session,
    conv_id: str,
    *,
    exclude_msg_id: str = "",
    limit: int = 8,
    max_chars: int = 2400,
) -> str:
    """Build a short recent-dialog digest for COMPOSITE (coordinator has no session history)."""
    rows = (
        db.query(Message)
        .filter(Message.conv_id == conv_id)
        .order_by(Message.created_at.desc())
        .limit(limit + 2)
        .all()
    )
    if not rows:
        return ""
    lines = []
    for msg in reversed(rows):
        if exclude_msg_id and msg.msg_id == exclude_msg_id:
            continue
        content = msg.content or {}
        text = (content.get("text") if isinstance(content, dict) else None) or ""
        text = str(text).strip()
        if not text:
            continue
        if msg.msg_type and msg.msg_type not in ("text", "push"):
            continue
        role = "用户" if (
            msg.sender_type == MemberType.HUMAN
            or (hasattr(msg.sender_type, "value") and msg.sender_type.value == "HUMAN")
        ) else "数字员工"
        snippet = text.replace("\n", " ").strip()
        if len(snippet) > 280:
            snippet = snippet[:280] + "…"
        lines.append(f"{role}: {snippet}")
        if len(lines) >= limit:
            # keep only the last `limit` lines chronologically already in order
            pass
    if len(lines) > limit:
        lines = lines[-limit:]
    if not lines:
        return ""
    blob = "\n".join(lines)
    if len(blob) > max_chars:
        blob = "…\n" + blob[-max_chars:]
    return blob


def _compose_im_prompt(db: Session, conv_id: str, text: str, *, exclude_msg_id: str = "") -> str:
    recent = _recent_conversation_context(db, conv_id, exclude_msg_id=exclude_msg_id)
    if not recent:
        return text
    return (
        f"【近期对话】\n{recent}\n\n"
        f"【当前用户消息】\n{text}"
    )


async def route_and_reply(
    db: Session,
    conv: Conversation,
    user_msg: Message,
    text: str,
    mention_worker_ids: List[str] = None,
    attachment_ids: List[str] = None,
) -> List[Message]:
    """Route message to digital workers via entry COMPOSITE agent."""
    members = db.query(ConversationMember).filter(
        ConversationMember.conv_id == conv.conv_id,
        ConversationMember.member_type == MemberType.WORKER,
    ).all()
    worker_ids = [m.member_id for m in members]
    workers = db.query(DigitalWorker).filter(
        DigitalWorker.worker_id.in_(worker_ids),
        DigitalWorker.status == WorkerStatus.ON_DUTY,
    ).all() if worker_ids else []

    targets = []
    if mention_worker_ids:
        targets = [w for w in workers if w.worker_id in mention_worker_ids]
    elif conv.type == ConvType.DIRECT:
        targets = workers
    else:
        targets = parse_mentions(text, workers)

    replies = []
    for w in targets:
        entry_id = (w.entry_agent_id or "").strip()
        if not entry_id:
            reply_text = "❌ 该数字员工尚未配置入口 Agent，请管理员执行「修复编排」"
            reply = Message(
                msg_id=gen_uuid(),
                conv_id=conv.conv_id,
                sender_type=MemberType.WORKER,
                sender_id=w.worker_id,
                msg_type="text",
                content={"text": reply_text, "format": "markdown"},
            )
            db.add(reply)
            replies.append(reply)
            continue
        sid = get_or_create_im_session(db, conv.conv_id, w, entry_id)
        # Exclude the just-persisted user message from "recent" by building context
        # from messages before this turn: pass current text separately.
        prompt = _compose_im_prompt(db, conv.conv_id, text, exclude_msg_id=user_msg.msg_id)
        chat_kwargs = {}
        if attachment_ids:
            chat_kwargs["attachment_ids"] = attachment_ids
        # Avoid duplicating the current user message if it is already the last row
        try:
            result = await vela_agent_client.achat(sid, prompt, **chat_kwargs)
            reply_text = ""
            if isinstance(result, dict):
                reply_text = result.get("reply") or result.get("content") or result.get("message") or ""
                if not reply_text and result.get("messages"):
                    for m in reversed(result["messages"]):
                        if m.get("role") == "assistant":
                            reply_text = m.get("content", "")
                            break
            if not reply_text:
                sess = vela_agent_client.get_session(sid)
                for m in reversed(sess.get("messages") or []):
                    if m.get("role") == "assistant":
                        reply_text = m.get("content", "")
                        break
            if not reply_text:
                reply_text = "（暂无回复）"
        except VelaAgentError as e:
            reply_text = f"❌ 处理失败：{e}"

        reply = Message(
            msg_id=gen_uuid(),
            conv_id=conv.conv_id,
            sender_type=MemberType.WORKER,
            sender_id=w.worker_id,
            msg_type="text",
            content={
                "text": reply_text,
                "format": "markdown",
                "entry_agent_id": entry_id,
                "reception_agent_id": w.reception_agent_id or "",
            },
        )
        db.add(reply)
        replies.append(reply)
    if replies:
        db.commit()
        for r in replies:
            db.refresh(r)
            await push_message(db, r)
    return replies


async def upload_agent_attachment(
    db: Session,
    conv_id: str,
    worker_id: str,
    filename: str,
    file_bytes: bytes,
    content_type: str = "application/octet-stream",
) -> dict:
    """Upload a file to the worker's IM agent session (vela-agent v0.9+ attachments)."""
    worker = db.query(DigitalWorker).filter(DigitalWorker.worker_id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="数字员工不存在")
    entry_id = (worker.entry_agent_id or "").strip()
    if not entry_id:
        raise HTTPException(status_code=400, detail="数字员工未配置入口 Agent")
    session_id = get_or_create_im_session(db, conv_id, worker, entry_id)
    try:
        result = vela_agent_client.upload_session_attachment(
            session_id, filename, file_bytes, content_type=content_type,
        )
    except VelaAgentError as e:
        raise HTTPException(status_code=502, detail=str(e))
    attachment_id = result.get("attachment_id") or result.get("id")
    return {
        "attachment_id": attachment_id,
        "session_id": session_id,
        "filename": filename,
    }
