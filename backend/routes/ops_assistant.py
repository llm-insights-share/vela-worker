"""Proxy the office ops assistant (vela-worker-ops-assistant) chat to vela-agent."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth_config import DATA_DIR
from deps import get_current_user
from models import HumanUser
from services.vela_agent_client import VelaAgentError, vela_agent_client

router = APIRouter(prefix="/api/v1/ops-assistant", tags=["ops-assistant"])

AGENT_NAME = "vela-worker-ops-assistant"
CONFIG_PATH = DATA_DIR / "ops_assistant.json"


class OpsMessageIn(BaseModel):
    message: str = Field(..., min_length=1)


class OpsApprovalIn(BaseModel):
    comment: str = ""


def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def resolve_agent() -> dict:
    cfg = _load_config()
    agent_id = (cfg.get("agent_id") or "").strip()
    agent = None
    if agent_id:
        try:
            agent = vela_agent_client.get_agent(agent_id)
        except VelaAgentError:
            agent = None
    if not agent:
        for status in ("PUBLISHED", None):
            items = vela_agent_client.list_agents(page_size=100, status=status) or []
            agent = next((a for a in items if a.get("name") == AGENT_NAME), None)
            if agent:
                break
    if not agent:
        raise HTTPException(
            status_code=404,
            detail="未找到办公操作助手。请在 backend 目录运行：python -m scripts.seed_ops_assistant",
        )
    return agent


def _raise_agent(exc: VelaAgentError):
    raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("")
def ops_meta(user: HumanUser = Depends(get_current_user)):
    try:
        agent = resolve_agent()
    except VelaAgentError as exc:
        _raise_agent(exc)
    return {
        "name": agent.get("name") or AGENT_NAME,
        "agent_id": agent.get("agent_id"),
        "description": agent.get("description") or "",
        "status": agent.get("status"),
        "ready": True,
    }


@router.post("/sessions", status_code=201)
def create_ops_session(user: HumanUser = Depends(get_current_user)):
    try:
        agent = resolve_agent()
        session = vela_agent_client.create_session(
            agent_id=agent["agent_id"],
            caller_type="HUMAN",
            caller_id=user.username or user.user_id,
        )
    except VelaAgentError as exc:
        _raise_agent(exc)
    return {
        "session_id": session.get("session_id"),
        "agent_id": agent["agent_id"],
        "status": session.get("status"),
    }


@router.get("/sessions/{session_id}")
def get_ops_session(session_id: str, user: HumanUser = Depends(get_current_user)):
    try:
        session = vela_agent_client.get_session(session_id)
        approvals = vela_agent_client.list_pending_approvals(session_id)
    except VelaAgentError as exc:
        _raise_agent(exc)
    return {
        "session_id": session.get("session_id") or session_id,
        "status": session.get("status"),
        "messages": session.get("messages") or [],
        "pending_approvals": approvals if isinstance(approvals, list) else (approvals or {}).get("items", []),
    }


@router.post("/sessions/{session_id}/messages")
def send_ops_message(
    session_id: str,
    data: OpsMessageIn,
    user: HumanUser = Depends(get_current_user),
):
    try:
        accepted = vela_agent_client.chat_async(session_id, data.message)
    except VelaAgentError as exc:
        _raise_agent(exc)
    return {"session_id": session_id, "accepted": True, "result": accepted}


@router.post("/sessions/{session_id}/approvals/{approval_id}/approve")
def approve_ops(
    session_id: str,
    approval_id: str,
    data: OpsApprovalIn,
    user: HumanUser = Depends(get_current_user),
):
    try:
        result = vela_agent_client.approve(
            session_id,
            approval_id,
            reviewer=user.username or user.name or "",
            comment=data.comment or "",
        )
    except VelaAgentError as exc:
        _raise_agent(exc)
    return result


@router.post("/sessions/{session_id}/approvals/{approval_id}/reject")
def reject_ops(
    session_id: str,
    approval_id: str,
    data: OpsApprovalIn,
    user: HumanUser = Depends(get_current_user),
):
    try:
        result = vela_agent_client.reject(
            session_id,
            approval_id,
            reviewer=user.username or user.name or "",
            comment=data.comment or "拒绝",
        )
    except VelaAgentError as exc:
        _raise_agent(exc)
    return result
