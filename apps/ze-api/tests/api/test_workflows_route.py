"""Tests for GET /api/v0/workflows/{id} and /api/v0/workflows/{id}/executions."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from ze_api.api.dependencies import require_api_key
from ze_api.api.routes.workflows import router
from ze_automation.workflow.types import (
    ActorContext,
    ActorSource,
    Branch,
    StepResult,
    Workflow,
    WorkflowExecution,
    WorkflowRevision,
    WorkflowStep,
)

API_KEY = "test-key"


def _workflow(steps: list[WorkflowStep]) -> Workflow:
    now = datetime.now(timezone.utc)
    return Workflow(
        id=uuid4(),
        name="Branching workflow",
        description="A workflow with branches",
        steps=steps,
        schedule=None,
        enabled=True,
        last_run_at=None,
        next_run_at=None,
        created_at=now,
        updated_at=now,
    )


def _make_app(
    workflow: Workflow, executions: list[WorkflowExecution] | None = None
) -> FastAPI:
    app = FastAPI()

    workflow_store = AsyncMock()
    workflow_store.get = AsyncMock(return_value=workflow)
    workflow_store.list_executions = AsyncMock(return_value=executions or [])
    workflow_store.get_execution = AsyncMock(
        return_value=executions[0] if executions else None
    )
    workflow_store.list_all = AsyncMock(return_value=[workflow])
    workflow_store.list_revisions = AsyncMock(return_value=[])

    container = SimpleNamespace(
        workflow_store=workflow_store,
        workflow_scheduler=AsyncMock(),
    )
    app.state.container = container

    app.dependency_overrides[require_api_key] = lambda: None
    app.include_router(router, prefix="/api/v0/workflows")
    return app


@pytest.mark.asyncio
async def test_get_workflow_includes_branch_fields():
    steps = [
        WorkflowStep(
            task="Check status",
            id="s0",
            branches=[
                Branch(condition="ok", to="s1"),
                Branch(condition="fail", to="FAIL"),
            ],
            default_next="s1",
        ),
        WorkflowStep(task="Notify", id="s1"),
    ]
    workflow = _workflow(steps)
    app = _make_app(workflow)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            f"/api/v0/workflows/{workflow.id}",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    step0 = data["steps"][0]
    assert step0["id"] == "s0"
    assert step0["default_next"] == "s1"
    assert step0["branches"] == [
        {"condition": "ok", "to": "s1"},
        {"condition": "fail", "to": "FAIL"},
    ]
    step1 = data["steps"][1]
    assert step1["id"] == "s1"
    assert step1["branches"] == []
    assert step1["default_next"] is None


@pytest.mark.asyncio
async def test_list_workflow_executions_includes_step_id_and_branch_taken():
    workflow = _workflow([WorkflowStep(task="Check status", id="s0")])
    execution = WorkflowExecution(
        id=uuid4(),
        workflow_id=workflow.id,
        status="completed",
        step_results=[
            StepResult(
                step_index=0,
                task="Check status",
                output="ok",
                success=True,
                error=None,
                duration_ms=10,
                step_id="s0",
                branch_taken="ok",
            )
        ],
        created_at=datetime.now(timezone.utc),
    )
    app = _make_app(workflow, executions=[execution])

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            f"/api/v0/workflows/{workflow.id}/executions",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    result = data[0]["step_results"][0]
    assert result["step_id"] == "s0"
    assert result["branch_taken"] == "ok"


@pytest.mark.asyncio
async def test_get_workflow_execution_includes_steps_snapshot():
    workflow = _workflow(
        [
            WorkflowStep(task="Original step", id="s0"),
            WorkflowStep(task="Second step", id="s1"),
        ]
    )
    execution = WorkflowExecution(
        id=uuid4(),
        workflow_id=workflow.id,
        status="completed",
        step_results=[],
        steps_snapshot=[WorkflowStep(task="Original step", id="s0")],
        created_at=datetime.now(timezone.utc),
    )
    app = _make_app(workflow, executions=[execution])

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            f"/api/v0/workflows/{workflow.id}/executions/{execution.id}",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["steps_snapshot"]) == 1
    assert data["steps_snapshot"][0]["task"] == "Original step"
    assert data["steps_snapshot"][0]["id"] == "s0"


@pytest.mark.asyncio
async def test_get_workflow_execution_by_id():
    workflow = _workflow([WorkflowStep(task="Check status", id="s0")])
    execution = WorkflowExecution(
        id=uuid4(),
        workflow_id=workflow.id,
        status="running",
        step_results=[],
        created_at=datetime.now(timezone.utc),
    )
    app = _make_app(workflow, executions=[execution])

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            f"/api/v0/workflows/{workflow.id}/executions/{execution.id}",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 200
    assert resp.json()["id"] == str(execution.id)
    assert resp.json()["status"] == "running"


@pytest.mark.asyncio
async def test_update_workflow_steps_success():
    steps = [
        WorkflowStep(task="Check status", id="s0", on_failure="continue"),
        WorkflowStep(task="Notify", id="s1"),
    ]
    workflow = _workflow(steps)
    app = _make_app(workflow)
    app.state.container.workflow_store.update_steps = AsyncMock()
    app.state.container.workflow_store.get = AsyncMock(return_value=workflow)

    payload = {
        "steps": [
            {
                "id": "s0",
                "task": "Check status",
                "on_failure": "continue",
                "branches": [],
            },
            {"id": "s1", "task": "Notify", "branches": []},
        ]
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.patch(
            f"/api/v0/workflows/{workflow.id}/steps",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json=payload,
        )

    assert resp.status_code == 200
    assert resp.json()["steps"][0]["on_failure"] == "continue"


@pytest.fixture
def mail_agent(monkeypatch):
    import ze_agents.registry as registry_mod
    import ze_agents.tool as tool_mod
    from ze_agents.base_agent import BaseAgent
    from ze_agents.registry import agent
    from ze_agents.reversibility import ToolReversibility
    from ze_agents.tool import ToolAccess, tool

    monkeypatch.setattr(registry_mod, "_registry", dict(registry_mod._registry))
    monkeypatch.setattr(tool_mod, "_tools", dict(tool_mod._tools))

    async def route_send_mail(to: str = "") -> str:
        return "sent"

    tool(
        access=ToolAccess.WRITE,
        description="send",
        reversibility=ToolReversibility.IRREVERSIBLE,
        effect_phrase="sent an email",
    )(route_send_mail)
    agent(
        type(
            "_RouteMail",
            (BaseAgent,),
            {"name": "route_mail", "description": "m", "tools": ["route_send_mail"]},
        )
    )


async def _patch_steps(approve_writes: bool):
    workflow = _workflow(
        [
            WorkflowStep(task="Draft", id="s0"),
            WorkflowStep(task="Send", id="s1", agent_hint="route_mail"),
        ]
    )
    app = _make_app(workflow)
    app.state.container.workflow_store.update_steps = AsyncMock()
    app.state.container.workflow_store.get = AsyncMock(return_value=workflow)
    payload = {
        "approve_writes": approve_writes,
        "steps": [
            {"id": "s0", "task": "Draft"},
            {"id": "s1", "task": "Send it", "agent_hint": "route_mail"},
        ],
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.patch(
            f"/api/v0/workflows/{workflow.id}/steps",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json=payload,
        )
    saved = app.state.container.workflow_store.update_steps.await_args.args[1]
    return resp, saved


@pytest.mark.asyncio
async def test_update_steps_clears_pre_approvals_and_lists_writes_needing_approval(
    mail_agent,
):
    resp, saved = await _patch_steps(approve_writes=False)
    assert resp.status_code == 200
    assert resp.json()["writes_needing_approval"] == [
        {"step_id": "s1", "agent": "route_mail", "tools": ["route_send_mail"]}
    ]
    assert [s.approved_writes for s in saved] == [[], []]


@pytest.mark.asyncio
async def test_update_steps_with_approve_writes_grants_the_changed_steps(mail_agent):
    resp, saved = await _patch_steps(approve_writes=True)
    assert resp.status_code == 200
    assert [s.approved_writes for s in saved] == [[], ["route_send_mail"]]


@pytest.mark.asyncio
async def test_update_workflow_steps_validation_error():
    workflow = _workflow([WorkflowStep(task="Check status", id="s0")])
    app = _make_app(workflow)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.patch(
            f"/api/v0/workflows/{workflow.id}/steps",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={
                "steps": [
                    {
                        "id": "s0",
                        "task": "Check status",
                        "branches": [{"condition": "x", "to": "missing"}],
                    }
                ]
            },
        )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_workflow_revisions_returns_newest_first():
    workflow = _workflow([WorkflowStep(task="Check status", id="s0")])
    revisions = [
        WorkflowRevision(
            id=uuid4(),
            workflow_id=workflow.id,
            revision_number=2,
            change_type="edited",
            steps_before=[WorkflowStep(task="old", id="s0")],
            steps_after=[WorkflowStep(task="new", id="s0")],
            summary="Step s0: task old → new",
            actor=ActorContext(
                source=ActorSource.AGENT, session_id="sess1", user_message_id="msg1"
            ),
            created_at=datetime.now(timezone.utc),
        ),
        WorkflowRevision(
            id=uuid4(),
            workflow_id=workflow.id,
            revision_number=1,
            change_type="created",
            steps_before=[],
            steps_after=[WorkflowStep(task="old", id="s0")],
            summary="Workflow created with 1 step(s)",
            actor=ActorContext(source=ActorSource.API),
            created_at=datetime.now(timezone.utc),
        ),
    ]
    app = _make_app(workflow)
    app.state.container.workflow_store.list_revisions = AsyncMock(
        return_value=revisions
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            f"/api/v0/workflows/{workflow.id}/revisions",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert [r["revision_number"] for r in data] == [2, 1]
    assert data[0]["actor_source"] == "agent"
    assert data[0]["actor_session_id"] == "sess1"
    assert data[1]["actor_source"] == "api"
    assert data[1]["actor_session_id"] is None


@pytest.mark.asyncio
async def test_list_workflow_revisions_404_for_unknown_workflow():
    workflow = _workflow([WorkflowStep(task="Check status", id="s0")])
    app = _make_app(workflow)
    app.state.container.workflow_store.get = AsyncMock(return_value=None)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            f"/api/v0/workflows/{uuid4()}/revisions",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cancel_workflow_execution_running():
    workflow = _workflow([WorkflowStep(task="Check status", id="s0")])
    execution = WorkflowExecution(
        id=uuid4(),
        workflow_id=workflow.id,
        status="running",
        step_results=[],
        created_at=datetime.now(timezone.utc),
    )
    app = _make_app(workflow, executions=[execution])
    scheduler = AsyncMock()
    scheduler.cancel_execution = AsyncMock(return_value="cancelled")
    app.state.container.workflow_scheduler = scheduler

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            f"/api/v0/workflows/{workflow.id}/executions/{execution.id}/cancel",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_workflow_execution_not_running():
    workflow = _workflow([WorkflowStep(task="Check status", id="s0")])
    execution = WorkflowExecution(
        id=uuid4(),
        workflow_id=workflow.id,
        status="completed",
        step_results=[],
        created_at=datetime.now(timezone.utc),
    )
    app = _make_app(workflow, executions=[execution])
    scheduler = AsyncMock()
    scheduler.cancel_execution = AsyncMock(return_value="not_running")
    app.state.container.workflow_scheduler = scheduler

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            f"/api/v0/workflows/{workflow.id}/executions/{execution.id}/cancel",
            headers={"Authorization": f"Bearer {API_KEY}"},
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "not_running"
