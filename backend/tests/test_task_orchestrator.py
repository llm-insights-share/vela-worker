"""Tests for item work orchestration (plan / schedule / execute path)."""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.orchestration_schema import (
    build_fallback_plan,
    extract_json_object,
    map_duty_to_agent,
    materialize_progress_steps,
    parse_work_plan,
    slice_time_window,
)
from services.task_orchestrator import should_orchestrate


def test_extract_json_object_raw_and_fenced():
    assert extract_json_object('{"intent":"x","steps":[]}')["intent"] == "x"
    text = '说明如下\n```json\n{"intent":"y","steps":[{"title":"a"}]}\n```\n'
    assert extract_json_object(text)["intent"] == "y"


def test_parse_work_plan_ok_and_fail():
    plan = parse_work_plan(
        '{"intent":"筛选简历","steps":[{"title":"收集","intent":"收集简历","duty_id":"d1","estimated_weight":2}]}'
    )
    assert plan["intent"] == "筛选简历"
    assert len(plan["steps"]) == 1
    assert plan["steps"][0]["duty_id"] == "d1"
    assert parse_work_plan("not json") is None
    assert parse_work_plan('{"intent":"x","steps":[]}') is None


def test_slice_time_window_proportional():
    start = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)
    end = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    slices = slice_time_window(start, end, [1, 3])
    assert len(slices) == 2
    assert slices[0][0] == start
    assert slices[-1][1] == end
    # first slice ~1 hour, second ~3 hours
    assert (slices[0][1] - slices[0][0]) == timedelta(hours=1)
    assert (slices[1][1] - slices[1][0]) == timedelta(hours=3)


def test_map_duty_and_fallback_plan():
    duty = SimpleNamespace(duty_id="duty-a", name="招聘", task_types=[], keywords=[])
    wda = SimpleNamespace(duty_id="duty-a", agent_id="agent-a", is_primary=True)
    duty_b = SimpleNamespace(duty_id="duty-b", name="其他", task_types=[], keywords=[])
    wda_b = SimpleNamespace(duty_id="duty-b", agent_id="agent-b", is_primary=False)
    duties = [(wda, duty)]
    did, dname, aid, aname = map_duty_to_agent("duty-a", duties, "entry-1")
    assert did == "duty-a" and aid == "agent-a"
    did2, _, aid2, _ = map_duty_to_agent("missing", duties, "entry-1")
    assert aid2 == "agent-a"
    _, _, aid3, _ = map_duty_to_agent("", [], "entry-1")
    assert aid3 == "entry-1"

    fb = build_fallback_plan(duties, "简历筛选")
    assert "intent" in fb and len(fb["steps"]) >= 3
    assert all(s.get("duty_id") == "duty-a" for s in fb["steps"])
    assert not any("协作执行" in (s.get("title") or "") for s in fb["steps"])

    # Even if multiple duties are passed, fallback stays on primary only
    fb2 = build_fallback_plan([(wda, duty), (wda_b, duty_b)], "立项资料收集")
    assert all(s.get("duty_id") == "duty-a" for s in fb2["steps"])
    assert not any("协作执行" in (s.get("title") or "") for s in fb2["steps"])
    assert not any(s.get("duty_id") == "duty-b" for s in fb2["steps"])


def test_materialize_progress_steps():
    duty = SimpleNamespace(duty_id="d1", name="主责", task_types=[], keywords=[])
    wda = SimpleNamespace(duty_id="d1", agent_id="ag1", is_primary=True)
    plan = {
        "intent": "完成事项",
        "steps": [
            {"title": "规划", "intent": "规划", "duty_id": "d1", "estimated_weight": 1},
            {"title": "执行", "intent": "执行", "duty_id": "d1", "estimated_weight": 2},
        ],
    }
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    end = datetime(2026, 9, 2, tzinfo=timezone.utc)
    intent, steps = materialize_progress_steps(plan, [(wda, duty)], "entry", start, end)
    assert intent == "完成事项"
    assert len(steps) == 2
    assert steps[0]["status"] == "pending"
    assert steps[0]["agent_id"] == "ag1"
    assert steps[0]["time_range"]
    assert steps[0]["key"] == "step-1"


def test_should_orchestrate():
    assert should_orchestrate(SimpleNamespace(item_id="i1", source="BPM")) is True
    assert should_orchestrate(SimpleNamespace(item_id="i1", source=SimpleNamespace(value="BPM"))) is True
    assert should_orchestrate(SimpleNamespace(item_id=None, source="BPM")) is False
    assert should_orchestrate(SimpleNamespace(item_id="i1", source="IM")) is False


@pytest.mark.asyncio
async def test_run_orchestrated_task_mocked(tmp_path, monkeypatch):
    from models import (
        TaskSource, TaskStatus, ProjectItemStatus, ProjectDocSource,
        ProjectOwnerType, gen_uuid, now_utc,
    )
    from services import task_orchestrator as orch

    task_id = "task-orch-1"
    item_id = "item-orch-1"
    worker_id = "worker-orch-1"
    project_id = "proj-orch-1"

    duty = SimpleNamespace(duty_id="duty-1", name="招聘助手", governance={}, task_types=[], keywords=[])
    wda = SimpleNamespace(duty_id="duty-1", agent_id="agent-duty", is_primary=True, status="ACTIVE")

    task = SimpleNamespace(
        task_id=task_id,
        worker_id=worker_id,
        item_id=item_id,
        project_id=project_id,
        duty_id="duty-1",
        source=TaskSource.BPM,
        title="简历筛选",
        instruction="请筛选简历",
        context={"project_name": "校园招聘"},
        status=TaskStatus.RECEIVED,
        status_detail="",
        progress_steps=[],
        progress_pct=0,
        progress_note="",
        result={},
        artifacts=[],
        agent_session_id="",
        tokens_used=0,
        conv_id=None,
        started_at=None,
        finished_at=None,
        reporter={},
        callback_url="",
        callback_events=[],
    )
    item = SimpleNamespace(
        item_id=item_id,
        project_id=project_id,
        name="简历筛选",
        description="筛选候选人",
        planned_start=datetime(2026, 9, 1, tzinfo=timezone.utc),
        planned_end=datetime(2026, 9, 3, tzinfo=timezone.utc),
        status=ProjectItemStatus.DELEGATED,
        progress_pct=0,
        meta={},
        completed_at=None,
        worker_id=worker_id,
        task_id=task_id,
    )
    worker = SimpleNamespace(
        worker_id=worker_id,
        name="招聘助手",
        entry_agent_id="agent-entry",
        governance_overrides={},
    )
    project = SimpleNamespace(project_id=project_id, name="校园招聘")

    class FakeQuery:
        def __init__(self, obj):
            self._obj = obj

        def filter(self, *a, **k):
            return self

        def first(self):
            return self._obj

    class FakeDB:
        def query(self, model):
            name = getattr(model, "__name__", str(model))
            if "WorkTask" in name or model is type(task):
                return FakeQuery(task)
            # use class name from models
            from models import WorkTask, DigitalWorker, ProjectItem, Project, Duty
            if model is WorkTask:
                return FakeQuery(task)
            if model is DigitalWorker:
                return FakeQuery(worker)
            if model is ProjectItem:
                return FakeQuery(item)
            if model is Project:
                return FakeQuery(project)
            if model is Duty:
                return FakeQuery(duty)
            return FakeQuery(None)

        def commit(self):
            pass

        def refresh(self, obj):
            pass

        def add(self, obj):
            pass

        def close(self):
            pass

    fake_db = FakeDB()

    plan_json = (
        '{"intent":"完成简历筛选","steps":['
        '{"title":"收集简历","intent":"收集","duty_id":"duty-1","estimated_weight":1},'
        '{"title":"筛选","intent":"筛选","duty_id":"duty-1","estimated_weight":2},'
        '{"title":"汇总报告","intent":"报告","duty_id":"duty-1","estimated_weight":1}'
        ']}'
    )

    async def fake_poll(db, task, worker, session_id, **kwargs):
        return {"ok": True, "summary": plan_json if "PLAN" in str(kwargs) or True else "步骤完成 产出名单.xlsx", "error": "", "canceled": False}

    call_n = {"n": 0}

    async def fake_poll2(db, task, worker, session_id, **kwargs):
        call_n["n"] += 1
        if call_n["n"] == 1:
            return {"ok": True, "summary": plan_json, "error": "", "canceled": False}
        if call_n["n"] <= 4:
            return {"ok": True, "summary": f"步骤{call_n['n']}完成，产出名单.xlsx", "error": "", "canceled": False}
        return {"ok": True, "summary": "# 报告\n全部完成", "error": "", "canceled": False}

    monkeypatch.setattr(orch, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(orch, "list_active_worker_duties", lambda db, wid: [(wda, duty)])
    monkeypatch.setattr(orch, "PROJECT_DOCS_DIR", tmp_path)

    docs_created = []

    def fake_create_doc(db, project, **kwargs):
        doc = {"doc_id": gen_uuid(), **kwargs, "file_path": kwargs.get("file_path")}
        docs_created.append(doc)
        return doc

    monkeypatch.setattr(orch, "create_project_document", fake_create_doc)
    monkeypatch.setattr(orch, "append_project_activity", lambda *a, **k: None)
    monkeypatch.setattr(orch, "sync_item_from_task", lambda *a, **k: None)
    monkeypatch.setattr(orch, "enqueue_webhook", lambda *a, **k: None)

    with patch("services.task_orchestrator.vela_agent_client") as client, \
         patch("services.task_runner.poll_session_until_done", new=AsyncMock(side_effect=fake_poll2)), \
         patch("services.task_runner._notify_task_update", new=AsyncMock()), \
         patch("services.task_runner._upsert_task_card", new=AsyncMock()), \
         patch("services.task_runner._post_result_card", new=AsyncMock()), \
         patch("services.task_runner._notify_inbox", MagicMock()), \
         patch("services.task_runner.start_queued_tasks", MagicMock()), \
         patch("services.task_runner._set_status", lambda db, t, s, d="": setattr(t, "status", s)), \
         patch("services.task_runner._add_event", MagicMock()):
        client.create_session.return_value = {"session_id": "sess-1"}
        client.achat_async = AsyncMock(return_value={})
        client.close_session = MagicMock()

        await orch.run_orchestrated_task(task_id)

    assert task.status == TaskStatus.COMPLETED
    assert len(task.progress_steps) >= 3
    assert all(s.get("status") == "completed" for s in task.progress_steps)
    assert task.result.get("report") or task.result.get("summary")
    assert task.artifacts
    assert docs_created


def test_run_task_routes_im_not_orchestrate():
    """IM tasks without item should not use should_orchestrate."""
    task = SimpleNamespace(item_id=None, source="IM")
    assert should_orchestrate(task) is False
