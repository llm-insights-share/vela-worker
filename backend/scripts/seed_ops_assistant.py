"""Idempotent seed for vela-worker-ops-assistant on vela-agent.

Run from backend/:
    python -m scripts.seed_ops_assistant
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from auth_config import DATA_DIR
from services.vela_agent_client import VelaAgentError, vela_agent_client

AGENT_NAME = "vela-worker-ops-assistant"
CONFIG_PATH = DATA_DIR / "ops_assistant.json"

OPS_PROMPT = """你是 Vela Worker「办公操作助手」(vela-worker-ops-assistant)。
你通过 worker_* 工具调用真实的 vela-worker API，完成项目、事项、委派、启动、暂停、继续执行、进度与数字员工查询。

硬性规则：
1. 必须使用工具获取或变更数据，禁止编造 ID、列表或操作结果；禁止声称已成功但未调用对应工具。
2. 写操作（创建项目/事项、委派、启动、暂停、继续）若缺少必填参数，必须先向用户追问补全，禁止自行猜测后宣称成功。
3. 委派后默认不自动启动，需用户明确要求再调用 worker_items_start。
4. 暂停用 worker_items_pause，继续用 worker_items_resume；不要用其他方式伪造状态。
5. 优先使用专用工具；仅在没有专用工具时使用 worker_run。
6. 回复简洁，用中文；展示工具返回的关键字段（名称、状态、id）。
"""

# name, display, description, function, schema, require_approval
TOOLS = [
    ("worker_run", "Worker·通用调用", "调用任意 worker API。method 如 GET/POST/PATCH；path 如 /projects；body_json 为 JSON 对象字符串。", "worker_run", {
        "type": "object",
        "properties": {
            "method": {"type": "string"},
            "path": {"type": "string"},
            "body_json": {"type": "string"},
        },
        "required": ["method", "path"],
    }, True),
    ("worker_workbench", "Worker·工作台摘要", "获取当前用户工作台（项目、员工、动态）。", "worker_workbench", {"type": "object", "properties": {}}, False),
    ("worker_projects_list", "Worker·列出项目", "列出当前用户的项目。", "worker_projects_list", {"type": "object", "properties": {}}, False),
    ("worker_projects_get", "Worker·项目详情", "按 project_id 获取项目。", "worker_projects_get", {
        "type": "object", "properties": {"project_id": {"type": "string"}}, "required": ["project_id"],
    }, False),
    ("worker_projects_create", "Worker·创建项目", "创建项目。", "worker_projects_create", {
        "type": "object",
        "properties": {"name": {"type": "string"}, "description": {"type": "string"}},
        "required": ["name"],
    }, True),
    ("worker_items_list", "Worker·列出事项", "列出项目下事项。", "worker_items_list", {
        "type": "object", "properties": {"project_id": {"type": "string"}}, "required": ["project_id"],
    }, False),
    ("worker_items_get", "Worker·事项详情", "按 item_id 获取事项与步骤。", "worker_items_get", {
        "type": "object", "properties": {"item_id": {"type": "string"}}, "required": ["item_id"],
    }, False),
    ("worker_items_create", "Worker·创建事项", "在项目下创建事项。", "worker_items_create", {
        "type": "object",
        "properties": {
            "project_id": {"type": "string"},
            "name": {"type": "string"},
            "description": {"type": "string"},
        },
        "required": ["project_id", "name"],
    }, True),
    ("worker_items_delegate", "Worker·委派事项", "把事项委派给数字员工（待确认启动）。", "worker_items_delegate", {
        "type": "object",
        "properties": {
            "item_id": {"type": "string"},
            "worker_id": {"type": "string"},
            "instruction": {"type": "string"},
            "task_type": {"type": "string"},
        },
        "required": ["item_id", "worker_id", "instruction"],
    }, True),
    ("worker_items_start", "Worker·确认启动", "启动已委派事项。", "worker_items_start", {
        "type": "object", "properties": {"item_id": {"type": "string"}}, "required": ["item_id"],
    }, True),
    ("worker_items_pause", "Worker·暂停事项", "暂停事项并把进行中步骤标为已暂停。", "worker_items_pause", {
        "type": "object", "properties": {"item_id": {"type": "string"}}, "required": ["item_id"],
    }, True),
    ("worker_items_resume", "Worker·继续执行", "从暂停处继续执行事项。", "worker_items_resume", {
        "type": "object", "properties": {"item_id": {"type": "string"}}, "required": ["item_id"],
    }, True),
    ("worker_workers_list", "Worker·数字员工列表", "列出数字员工。", "worker_workers_list", {
        "type": "object", "properties": {"page_size": {"type": "integer"}},
    }, False),
    ("worker_workers_get", "Worker·数字员工详情", "按 worker_id 获取数字员工。", "worker_workers_get", {
        "type": "object", "properties": {"worker_id": {"type": "string"}}, "required": ["worker_id"],
    }, False),
    ("worker_tasks_list", "Worker·任务列表", "列出工作任务，可按 worker_id/status 过滤。", "worker_tasks_list", {
        "type": "object",
        "properties": {
            "worker_id": {"type": "string"},
            "status": {"type": "string"},
            "page_size": {"type": "integer"},
        },
    }, False),
    ("worker_tasks_get", "Worker·任务详情", "按 task_id 获取任务与步骤。", "worker_tasks_get", {
        "type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"],
    }, False),
]


def _items(data):
    if isinstance(data, dict):
        return data.get("items") or []
    return data or []


def _find_tool(name: str):
    for page in range(1, 8):
        data = vela_agent_client._get("/tools", {"page": page, "page_size": 100})
        items = data.get("items", []) if isinstance(data, dict) else (data or [])
        for t in items:
            if t.get("name") == name:
                return t
        if len(items) < 100:
            break
    return None


def _upsert_tool(name, display, desc, fn, schema):
    payload = {
        "name": name,
        "display_name": display,
        "description": desc,
        "tool_type": "local_python",
        "config": {"module": "services.worker_ops_tools", "function": fn},
        "parameters_schema": schema,
    }
    existing = _find_tool(name)
    if existing:
        return vela_agent_client.update_tool(existing["tool_id"], {
            "display_name": display,
            "description": desc,
            "config": payload["config"],
            "parameters_schema": schema,
            "status": "ACTIVE",
        })
    return vela_agent_client.create_tool(payload)


def _model_service_id() -> str:
    items = _items(vela_agent_client.list_model_services())
    if not items:
        raise SystemExit("vela-agent 没有可用模型服务，无法创建操作助手")
    return items[0].get("model_service_id") or items[0].get("id")


def _find_agent():
    for status in ("PUBLISHED", None):
        items = vela_agent_client.list_agents(page_size=100, status=status)
        for a in items or []:
            if a.get("name") == AGENT_NAME:
                return a
    return None


def seed() -> dict:
    bindings = []
    for name, display, desc, fn, schema, need_approval in TOOLS:
        tool = _upsert_tool(name, display, desc, fn, schema)
        bindings.append({"tool_id": tool["tool_id"], "require_approval": bool(need_approval)})

    model_service_id = _model_service_id()
    body = {
        "description": "办公操作助手：通过对话执行项目、事项、委派与启停",
        "system_prompt": OPS_PROMPT,
        "model_service_id": model_service_id,
        "tags": ["platform", "ops", "worker", "builtin"],
        "max_iterations": 20,
        "agent_type": "SINGLE",
        "composition_config": {"tool_loading": {"enabled": True, "mode": "eager"}},
        "change_summary": "办公操作助手工具与提示词",
    }
    agent = _find_agent()
    if agent:
        agent = vela_agent_client.update_agent(agent["agent_id"], body)
    else:
        agent = vela_agent_client.create_agent({
            "name": AGENT_NAME,
            **body,
        })
    agent_id = agent["agent_id"]
    vela_agent_client.bind_tools(agent_id, bindings)
    try:
        vela_agent_client.publish_agent(agent_id, change_summary="发布办公操作助手")
    except VelaAgentError:
        vela_agent_client.republish_agent(agent_id)

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"agent_id": agent_id, "name": AGENT_NAME}
    CONFIG_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    try:
        summary = seed()
    except VelaAgentError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
