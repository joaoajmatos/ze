"""Undo payloads for create/enable/disable workflow (Phase 180)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import ze_automation.agents.workflow.tools as tools
from ze_agents.errors import WorkflowPlanError
from ze_automation.agents.workflow.agent import WorkflowManagerAgent
from ze_automation.workflow.types import Workflow, WorkflowStep


def _workflow(enabled: bool) -> Workflow:
    now = datetime.now(tz=timezone.utc)
    return Workflow(
        id=uuid4(),
        name="daily-news",
        description="d",
        steps=[WorkflowStep(task="Search")],
        schedule=None,
        enabled=enabled,
        last_run_at=None,
        next_run_at=None,
        created_at=now,
        updated_at=now,
    )


async def test_create_workflow_returns_undo_payload():
    store = AsyncMock()
    store.create = AsyncMock(return_value=uuid4())
    planner = MagicMock()
    planner.plan = AsyncMock(return_value=[WorkflowStep(task="Do it", id="s0")])
    planner.extract_schedule = AsyncMock(return_value=None)
    result = await tools.create_workflow(
        store, planner, AsyncMock(), "new-flow", "Do it"
    )
    assert result["undo"] == {"workflow_name": "new-flow"}


async def test_create_workflow_no_payload_on_plan_error():
    planner = MagicMock()
    planner.plan = AsyncMock(side_effect=WorkflowPlanError("nope"))
    result = await tools.create_workflow(
        AsyncMock(), planner, AsyncMock(), "new-flow", "Do it"
    )
    assert "error" in result
    assert "undo" not in result


async def test_enable_workflow_payload_when_it_was_disabled():
    store = AsyncMock()
    store.get_by_name = AsyncMock(return_value=_workflow(enabled=False))
    result = await tools.enable_workflow(store, AsyncMock(), "daily-news")
    assert result["undo"] == {"workflow_name": "daily-news"}


async def test_enable_workflow_no_payload_when_already_enabled():
    store = AsyncMock()
    store.get_by_name = AsyncMock(return_value=_workflow(enabled=True))
    result = await tools.enable_workflow(store, AsyncMock(), "daily-news")
    assert result["enabled"] is True
    assert "undo" not in result


async def test_enable_workflow_no_payload_when_missing():
    store = AsyncMock()
    store.get_by_name = AsyncMock(return_value=None)
    result = await tools.enable_workflow(store, AsyncMock(), "daily-news")
    assert "error" in result
    assert "undo" not in result


async def test_disable_workflow_payload_when_it_was_enabled():
    store = AsyncMock()
    store.get_by_name = AsyncMock(return_value=_workflow(enabled=True))
    result = await tools.disable_workflow(store, AsyncMock(), "daily-news")
    assert result["undo"] == {"workflow_name": "daily-news"}


async def test_disable_workflow_no_payload_when_already_disabled():
    store = AsyncMock()
    store.get_by_name = AsyncMock(return_value=_workflow(enabled=False))
    result = await tools.disable_workflow(store, AsyncMock(), "daily-news")
    assert result["enabled"] is False
    assert "undo" not in result


async def test_disable_workflow_no_payload_when_missing():
    store = AsyncMock()
    store.get_by_name = AsyncMock(return_value=None)
    result = await tools.disable_workflow(store, AsyncMock(), "daily-news")
    assert "error" in result
    assert "undo" not in result


def test_tool_deps_has_the_keys_the_loop_used():
    store, planner, scheduler = MagicMock(), MagicMock(), MagicMock()
    agent = WorkflowManagerAgent(
        openrouter_client=AsyncMock(),
        workflow_store=store,
        workflow_planner=planner,
        workflow_scheduler=scheduler,
    )
    assert agent.tool_deps() == {
        "store": store,
        "planner": planner,
        "scheduler": scheduler,
    }
