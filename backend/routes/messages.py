from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from database import get_db
from models import (
    Conversation, ConversationMember, Message, DigitalWorker, HumanUser,
    MemberType, WorkerStatus, gen_uuid,
)
from schemas import MessageCreate, ApprovalAction, InfoReply
from deps import get_current_user
from services import im_service
from services.task_runner import create_and_start_task, schedule_task
from services.hitl_bridge import handle_approval, handle_info_reply
from models import TaskSource

router = APIRouter(prefix="/api/v1/conversations", tags=["messages"])


@router.get("/{conv_id}/messages")
def list_messages(
    conv_id: str,
    before: str = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: HumanUser = Depends(get_current_user),
):
    m = db.query(ConversationMember).filter(
        ConversationMember.conv_id == conv_id,
        ConversationMember.member_type == MemberType.HUMAN,
        ConversationMember.member_id == user.user_id,
    ).first()
    if not m:
        raise HTTPException(status_code=403, detail="非会话成员")
    q = db.query(Message).filter(Message.conv_id == conv_id)
    if before:
        ref = db.query(Message).filter(Message.msg_id == before).first()
        if ref:
            q = q.filter(Message.created_at < ref.created_at)
    msgs = q.order_by(Message.created_at.desc()).limit(limit).all()
    msgs.reverse()
    return [im_service.message_to_dict(db, x) for x in msgs]


@router.post("/{conv_id}/messages")
async def send_message(
    conv_id: str,
    data: MessageCreate,
    db: Session = Depends(get_db),
    user: HumanUser = Depends(get_current_user),
):
    conv = db.query(Conversation).filter(Conversation.conv_id == conv_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")
    m = db.query(ConversationMember).filter(
        ConversationMember.conv_id == conv_id,
        ConversationMember.member_type == MemberType.HUMAN,
        ConversationMember.member_id == user.user_id,
    ).first()
    if not m:
        raise HTTPException(status_code=403, detail="非会话成员")

    user_msg = Message(
        msg_id=gen_uuid(),
        conv_id=conv_id,
        sender_type=MemberType.HUMAN,
        sender_id=user.user_id,
        msg_type=data.msg_type or "text",
        content={"text": data.content, "format": "txt"},
    )
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)
    await im_service.push_message(db, user_msg)

    # Task assignment path
    if data.as_task:
        worker_id = (data.mention_worker_ids or [None])[0]
        if not worker_id:
            raise HTTPException(status_code=400, detail="指派任务需指定数字员工")
        worker = db.query(DigitalWorker).filter(
            DigitalWorker.worker_id == worker_id,
            DigitalWorker.status == WorkerStatus.ON_DUTY,
        ).first()
        if not worker:
            raise HTTPException(status_code=404, detail="数字员工不可用")
        task = create_and_start_task(
            db,
            worker=worker,
            source=TaskSource.IM,
            title=data.task_title or data.content[:40],
            instruction=data.content,
            task_type=data.task_type or "",
            conv_id=conv_id,
            reporter={"type": "HUMAN", "user_id": user.user_id, "name": user.name},
        )
        # ensure background starts
        schedule_task(task.task_id)
        return {
            "message": im_service.message_to_dict(db, user_msg),
            "task_id": task.task_id,
        }

    # Q&A routing
    replies = await im_service.route_and_reply(
        db, conv, user_msg, data.content,
        mention_worker_ids=data.mention_worker_ids or [],
        attachment_ids=data.attachment_ids or [],
    )
    return {
        "message": im_service.message_to_dict(db, user_msg),
        "replies": [im_service.message_to_dict(db, r) for r in replies],
    }


@router.post("/{conv_id}/agent-attachments")
async def upload_agent_attachment(
    conv_id: str,
    worker_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: HumanUser = Depends(get_current_user),
):
    m = db.query(ConversationMember).filter(
        ConversationMember.conv_id == conv_id,
        ConversationMember.member_type == MemberType.HUMAN,
        ConversationMember.member_id == user.user_id,
    ).first()
    if not m:
        raise HTTPException(status_code=403, detail="非会话成员")
    content = await file.read()
    return await im_service.upload_agent_attachment(
        db,
        conv_id,
        worker_id,
        file.filename or "upload.bin",
        content,
        content_type=file.content_type or "application/octet-stream",
    )


@router.post("/messages/{msg_id}/approval")
async def approve_message_card(
    msg_id: str,
    data: ApprovalAction,
    db: Session = Depends(get_db),
    user: HumanUser = Depends(get_current_user),
):
    return await handle_approval(
        db,
        msg_id=msg_id,
        approved=data.approved,
        reviewer=user.user_id,
        comment=data.comment,
        otp_code=data.otp_code,
        param_values=data.param_values,
    )


@router.post("/tasks/{task_id}/info-reply")
async def info_reply(
    task_id: str,
    data: InfoReply,
    db: Session = Depends(get_db),
    user: HumanUser = Depends(get_current_user),
):
    return await handle_info_reply(db, task_id=task_id, message=data.message, user_id=user.user_id)
