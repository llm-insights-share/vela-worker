"""Orchestration contracts: progress_steps shape, plan JSON parse, schedule slicing."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple


STEP_STATUSES = ("pending", "queued", "running", "completed", "failed")


def _iso(dt: Optional[datetime]) -> str:
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _parse_dt(value) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value.strip():
        try:
            raw = value.strip().replace("Z", "+00:00")
            dt = datetime.fromisoformat(raw)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def format_time_range(start: Optional[datetime], end: Optional[datetime]) -> str:
    if not start and not end:
        return ""

    def _fmt(dt: datetime) -> str:
        local = dt.astimezone() if dt.tzinfo else dt
        return local.strftime("%m-%d %H:%M")

    if start and end:
        return f"{_fmt(start)} - {_fmt(end)}"
    if start:
        return _fmt(start)
    return _fmt(end)


def extract_json_object(text: str) -> Optional[dict]:
    """Pull the first JSON object from model output (raw or fenced)."""
    if not text:
        return None
    raw = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", raw, re.IGNORECASE)
    if fence:
        raw = fence.group(1)
    else:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            raw = raw[start : end + 1]
        else:
            return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def normalize_plan_steps(raw_steps: Any) -> List[dict]:
    if not isinstance(raw_steps, list):
        return []
    out = []
    for i, s in enumerate(raw_steps):
        if not isinstance(s, dict):
            continue
        title = (s.get("title") or s.get("name") or f"步骤 {i + 1}").strip()
        intent = (s.get("intent") or s.get("description") or title).strip()
        weight = s.get("estimated_weight", s.get("weight", 1))
        try:
            weight = float(weight)
        except (TypeError, ValueError):
            weight = 1.0
        if weight <= 0:
            weight = 1.0
        out.append({
            "title": title[:200],
            "intent": intent[:1000],
            "duty_id": (s.get("duty_id") or "").strip(),
            "estimated_weight": weight,
        })
    return out


def parse_work_plan(text: str) -> Optional[dict]:
    """
    Parse planner output into {intent, steps:[{title,intent,duty_id,estimated_weight}]}.
    Returns None if unusable.
    """
    data = extract_json_object(text)
    if not data:
        return None
    steps = normalize_plan_steps(data.get("steps") or data.get("plan") or [])
    if not steps:
        return None
    intent = (data.get("intent") or data.get("summary") or steps[0]["intent"]).strip()
    return {"intent": intent[:500], "steps": steps}


def slice_time_window(
    start: Optional[datetime],
    end: Optional[datetime],
    weights: List[float],
    *,
    default_hours: float = 8.0,
) -> List[Tuple[datetime, datetime]]:
    """Split [start,end] into contiguous slices proportional to weights."""
    now = datetime.now(timezone.utc)
    if not start:
        start = now
    if not end or end <= start:
        end = start + timedelta(hours=default_hours)
    if not weights:
        return []
    total = sum(weights) or float(len(weights))
    span = (end - start).total_seconds()
    slices = []
    cursor = start
    for i, w in enumerate(weights):
        if i == len(weights) - 1:
            piece_end = end
        else:
            piece_end = cursor + timedelta(seconds=span * (w / total))
        slices.append((cursor, piece_end))
        cursor = piece_end
    return slices


def map_duty_to_agent(
    duty_id: str,
    duties: List[Tuple[Any, Any]],
    entry_agent_id: str,
) -> Tuple[str, str, str, str]:
    """
    Returns (duty_id, duty_name, agent_id, agent_name).
    duties: list of (WorkerDutyAgent, Duty)
    """
    entry = (entry_agent_id or "").strip()
    if duty_id:
        for wda, duty in duties:
            if duty.duty_id == duty_id:
                agent_id = (wda.agent_id or "").strip() or entry
                return (
                    duty.duty_id,
                    duty.name or "",
                    agent_id,
                    duty.name or "Agent",
                )
    # fallback primary / first
    if duties:
        wda, duty = duties[0]
        for w, d in duties:
            if getattr(w, "is_primary", False):
                wda, duty = w, d
                break
        agent_id = (wda.agent_id or "").strip() or entry
        return duty.duty_id, duty.name or "", agent_id, duty.name or "Agent"
    return "", "", entry, "入口Agent"


def build_fallback_plan(duties: List[Tuple[Any, Any]], item_name: str = "") -> dict:
    """Heuristic steps for the current item's matched duty only (no cross-duty collab)."""
    primary = None
    if duties:
        primary = duties[0]
        for wda, duty in duties:
            if getattr(wda, "is_primary", False):
                primary = (wda, duty)
                break
    primary_duty_id = primary[1].duty_id if primary else ""
    primary_name = primary[1].name if primary else "主责"
    name = item_name or "事项"
    steps = [
        {
            "title": "识别事项意图",
            "intent": f"分析「{name}」的目标、约束与交付要求，明确工作意图。",
            "duty_id": primary_duty_id,
            "estimated_weight": 1,
        },
        {
            "title": f"执行主责工作（{primary_name}）",
            "intent": f"按职责「{primary_name}」完成「{name}」的核心执行工作。",
            "duty_id": primary_duty_id,
            "estimated_weight": 3,
        },
        {
            "title": "汇总工作报告",
            "intent": f"汇总「{name}」执行结果，整理工作报告与产出清单。",
            "duty_id": primary_duty_id,
            "estimated_weight": 1,
        },
    ]
    return {
        "intent": f"完成事项「{name}」并提交工作报告",
        "steps": steps,
    }


def materialize_progress_steps(
    plan: dict,
    duties: List[Tuple[Any, Any]],
    entry_agent_id: str,
    planned_start=None,
    planned_end=None,
) -> Tuple[str, List[dict]]:
    """
    Convert a plan into persisted progress_steps list.
    Returns (intent, steps).
    """
    intent = (plan.get("intent") or "").strip() or "执行委派事项"
    raw_steps = plan.get("steps") or []
    weights = [float(s.get("estimated_weight") or 1) for s in raw_steps]
    start = _parse_dt(planned_start)
    end = _parse_dt(planned_end)
    slices = slice_time_window(start, end, weights)

    steps: List[Dict[str, Any]] = []
    for i, s in enumerate(raw_steps):
        duty_id, duty_name, agent_id, agent_name = map_duty_to_agent(
            s.get("duty_id") or "", duties, entry_agent_id
        )
        ps, pe = slices[i] if i < len(slices) else (None, None)
        steps.append({
            "key": f"step-{i + 1}",
            "title": s.get("title") or f"步骤 {i + 1}",
            "intent": s.get("intent") or "",
            "status": "pending",
            "duty_id": duty_id,
            "duty_name": duty_name,
            "agent_id": agent_id,
            "agent_name": agent_name,
            "planned_start": _iso(ps),
            "planned_end": _iso(pe),
            "time_range": format_time_range(ps, pe),
            "started_at": "",
            "finished_at": "",
            "detail": "",
            "result": "",
            "outputs": [],
        })
    return intent, steps


def build_planning_prompt(
    *,
    item_name: str,
    item_description: str,
    instruction: str,
    planned_start,
    planned_end,
    project_name: str,
    duties: List[Tuple[Any, Any]],
) -> str:
    duty_lines = []
    for wda, duty in duties:
        duty_lines.append(
            f"- duty_id={duty.duty_id} name={duty.name} "
            f"agent_id={wda.agent_id or ''} "
            f"task_types={','.join(duty.task_types or [])} "
            f"keywords={','.join(duty.keywords or [])}"
        )
    ps = _iso(_parse_dt(planned_start)) or "(未指定)"
    pe = _iso(_parse_dt(planned_end)) or "(未指定)"
    return (
        "你是数字员工的工作编排助手。请识别事项意图，并拆分为可执行工作步骤。\n"
        "只返回一个 JSON 对象，不要 markdown，不要解释。格式：\n"
        '{"intent":"一句话意图","steps":[{"title":"步骤名","intent":"本步目标",'
        '"duty_id":"可选职责ID","estimated_weight":1}]}\n'
        "约束：\n"
        "- steps 数量 2~6\n"
        "- 只拆解【当前事项】本身的工作步骤，禁止引入其他事项或其他无关职责的协作步骤\n"
        "- duty_id 必须来自可用职责列表；本事项通常只用列表中的匹配职责\n"
        "- estimated_weight 为正数，用于时间分配\n"
        "- 最后一步应体现汇总/报告\n\n"
        f"【项目】{project_name or '-'}\n"
        f"【事项】{item_name}\n"
        f"【描述】{item_description or '-'}\n"
        f"【委派说明】{instruction or '-'}\n"
        f"【计划开始】{ps}\n"
        f"【计划结束】{pe}\n"
        "【可用职责】\n"
        + ("\n".join(duty_lines) if duty_lines else "(无)")
    )
