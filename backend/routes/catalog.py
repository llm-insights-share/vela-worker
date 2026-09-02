"""Proxy catalog from vela-agent for role configuration forms."""
from fastapi import APIRouter, Depends, HTTPException
from deps import get_current_user
from models import HumanUser
from services.vela_agent_client import vela_agent_client, VelaAgentError

router = APIRouter(prefix="/api/v1/catalog", tags=["catalog"])


@router.get("/model-services")
def catalog_model_services(user: HumanUser = Depends(get_current_user)):
    try:
        return vela_agent_client.list_model_services()
    except VelaAgentError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/skills")
def catalog_skills(user: HumanUser = Depends(get_current_user)):
    try:
        return vela_agent_client.list_skills()
    except VelaAgentError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/tools")
def catalog_tools(user: HumanUser = Depends(get_current_user)):
    try:
        return vela_agent_client.list_tools()
    except VelaAgentError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/knowledge-bases")
def catalog_kbs(user: HumanUser = Depends(get_current_user)):
    try:
        return vela_agent_client.list_knowledge_bases()
    except VelaAgentError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/agents")
def catalog_agents(user: HumanUser = Depends(get_current_user)):
    """List vela-agent Agents for duty template selection."""
    try:
        # Prefer published; fall back to all non-deleted
        items = vela_agent_client.list_agents(page_size=100, status="PUBLISHED")
        if not items:
            items = vela_agent_client.list_agents(page_size=100)
        # Prefer template agents: exclude auto-created digital-worker instances
        templates = [a for a in items if "digital-worker" not in (a.get("tags") or [])]
        return templates or items
    except VelaAgentError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/agent-health")
def agent_health(user: HumanUser = Depends(get_current_user)):
    return vela_agent_client.check_health()
