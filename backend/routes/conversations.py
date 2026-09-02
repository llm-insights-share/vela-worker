from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Conversation, ConversationMember, HumanUser, MemberType
from schemas import ConversationCreate, MemberInput
from deps import get_current_user
from services import im_service

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


@router.get("")
def list_conversations(db: Session = Depends(get_db), user: HumanUser = Depends(get_current_user)):
    member_rows = db.query(ConversationMember).filter(
        ConversationMember.member_type == MemberType.HUMAN,
        ConversationMember.member_id == user.user_id,
    ).all()
    conv_ids = [m.conv_id for m in member_rows]
    if not conv_ids:
        return []
    convs = db.query(Conversation).filter(Conversation.conv_id.in_(conv_ids)).order_by(Conversation.created_at.desc()).all()
    return [im_service.conversation_to_dict(db, c, user_id=user.user_id) for c in convs]


@router.post("", status_code=201)
def create_conversation(
    data: ConversationCreate,
    db: Session = Depends(get_db),
    user: HumanUser = Depends(get_current_user),
):
    members = [{"member_type": m.member_type, "member_id": m.member_id} for m in data.members]
    conv = im_service.create_conversation(
        db,
        conv_type=data.type,
        name=data.name,
        owner_id=user.user_id,
        members=members,
    )
    return im_service.conversation_to_dict(db, conv, user_id=user.user_id)


@router.get("/{conv_id}")
def get_conversation(conv_id: str, db: Session = Depends(get_db), user: HumanUser = Depends(get_current_user)):
    conv = db.query(Conversation).filter(Conversation.conv_id == conv_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")
    # membership check
    m = db.query(ConversationMember).filter(
        ConversationMember.conv_id == conv_id,
        ConversationMember.member_type == MemberType.HUMAN,
        ConversationMember.member_id == user.user_id,
    ).first()
    if not m:
        raise HTTPException(status_code=403, detail="非会话成员")
    return im_service.conversation_to_dict(db, conv, user_id=user.user_id)


@router.post("/{conv_id}/read")
def mark_read(conv_id: str, db: Session = Depends(get_db), user: HumanUser = Depends(get_current_user)):
    return im_service.mark_conversation_read(db, conv_id, user.user_id)


@router.post("/{conv_id}/members")
def add_members(
    conv_id: str,
    members: list[MemberInput],
    db: Session = Depends(get_db),
    user: HumanUser = Depends(get_current_user),
):
    im_service.add_members(db, conv_id, [{"member_type": m.member_type, "member_id": m.member_id} for m in members])
    conv = db.query(Conversation).filter(Conversation.conv_id == conv_id).first()
    return im_service.conversation_to_dict(db, conv, user_id=user.user_id)
