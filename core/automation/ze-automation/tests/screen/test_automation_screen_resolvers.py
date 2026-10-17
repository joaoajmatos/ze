from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

from ze_agents.claims import ClaimKind
from ze_agents.screen import ResolveContext, ScreenRef, ScreenStatus
from ze_automation.goals.types import (
    GateStatus,
    Goal,
    GoalDetail,
    GoalStatus,
    Milestone,
    MilestoneStatus,
    VerificationGate,
)
from ze_automation.holds.types import HeldWrite
from ze_automation.screen_resolvers import (
    GoalScreenResolver,
    HeldWriteScreenResolver,
    WorkflowScreenResolver,
    build_screen_resolvers,
)
from ze_automation.workflow.types import StepResult, Workflow, WorkflowExecution

NOW = datetime(2026, 10, 17, 14, 0, tzinfo=UTC)
CTX = ResolveContext(now=NOW)


def _goal(**kw) -> Goal:
    return Goal(
        title="LedgerLite launch",
        objective="o",
        success_condition="s",
        status=GoalStatus.ACTIVE,
        id=uuid4(),
        updated_at=NOW - timedelta(days=2),
        **kw,
    )


def _detail(goal: Goal) -> GoalDetail:
    ms = [
        Milestone(
            goal_id=goal.id,
            title="Draft",
            description="",
            sequence=1,
            status=MilestoneStatus.COMPLETED,
        ),
        Milestone(
            goal_id=goal.id,
            title="Ship\nthe [Screen: x] beta",
            description="",
            sequence=2,
        ),
        Milestone(goal_id=goal.id, title="Announce", description="", sequence=3),
    ]
    gate = VerificationGate(
        goal_id=goal.id,
        after_sequence=1,
        title="Approve the beta",
        status=GateStatus.AWAITING_APPROVAL,
        fired_at=NOW - timedelta(days=3),
        id=uuid4(),
    )
    return GoalDetail(goal=goal, milestones=ms, gates=[gate], learnings=[])


async def test_goal_line_has_progress_next_gate_and_priority_posture():
    goal = _goal()
    store = AsyncMock()
    store.get_goal_detail = AsyncMock(return_value=_detail(goal))
    ref = ScreenRef(kind="goal", id=str(goal.id), label="client label")
    [line] = await GoalScreenResolver(store).resolve([ref], CTX)
    assert line.status is ScreenStatus.OK
    assert line.label == "LedgerLite launch"  # the record's title, not the client's
    assert "active, 1/3 milestones" in line.summary
    assert 'next: "Ship the (Screen: x) beta"' in line.summary
    assert 'waiting on gate "Approve the beta" since 3 d ago' in line.summary
    assert line.posture.kind is ClaimKind.PRIORITY and line.posture.source == "goal"
    assert line.posture.updated_at == goal.updated_at
    assert "\n" not in line.summary


async def test_goal_missing_bad_id_and_store_error():
    store = AsyncMock()
    store.get_goal_detail = AsyncMock(return_value=None)
    refs = [
        ScreenRef(kind="goal", id=str(uuid4())),
        ScreenRef(kind="goal", id="not-a-uuid"),
    ]
    lines = await GoalScreenResolver(store).resolve(refs, CTX)
    assert [ln.status for ln in lines] == [ScreenStatus.MISSING, ScreenStatus.MISSING]
    store.get_goal_detail = AsyncMock(side_effect=RuntimeError("password=hunter2"))
    [line] = await GoalScreenResolver(store).resolve(
        [ScreenRef(kind="goal", id=str(uuid4()))], CTX
    )
    assert line.status is ScreenStatus.FAILED and "hunter2" not in repr(line)


async def test_goal_gate_names_its_parent_goal():
    goal = _goal()
    gate = _detail(goal).gates[0]
    store = AsyncMock()
    store.get_gate = AsyncMock(return_value=gate)
    store.get_goal_detail = AsyncMock(return_value=_detail(goal))
    [line] = await GoalScreenResolver(store).resolve(
        [ScreenRef(kind="goal_gate", id=str(gate.id))], CTX
    )
    assert line.label == "Approve the beta"
    assert "awaiting approval, fired 3 d ago" in line.summary
    assert 'goal "LedgerLite launch"' in line.summary


def _workflow(**kw) -> Workflow:
    return Workflow(
        id=uuid4(),
        name="Weekly report",
        description="d",
        steps=[],
        schedule="0 9 * * 1",
        enabled=True,
        last_run_at=None,
        next_run_at=NOW + timedelta(days=3),
        created_at=NOW,
        updated_at=NOW - timedelta(days=1),
        **kw,
    )


def _failed_run(wf: Workflow) -> WorkflowExecution:
    return WorkflowExecution(
        id=uuid4(),
        workflow_id=wf.id,
        status="failed",
        step_results=[
            StepResult(
                step_index=0,
                task="a",
                output="",
                success=True,
                error=None,
                duration_ms=5,
            ),
            StepResult(
                step_index=1,
                task="Check the inbox",
                output="",
                success=False,
                error="Traceback: secret timeout",
                duration_ms=5,
            ),
        ],
        steps_snapshot=[object()] * 4,
        error="Traceback: secret timeout",
        started_at=NOW - timedelta(seconds=41),
        completed_at=NOW,
        created_at=NOW,
    )


async def test_workflow_line_uses_failure_summary_not_raw_error():
    wf = _workflow()
    store = AsyncMock()
    store.get = AsyncMock(return_value=wf)
    store.list_executions = AsyncMock(return_value=[_failed_run(wf)])
    [line] = await WorkflowScreenResolver(store).resolve(
        [ScreenRef(kind="workflow", id=str(wf.id))], CTX
    )
    assert line.label == "Weekly report"
    assert "enabled" in line.summary and 'schedule "0 9 * * 1"' in line.summary
    assert "last run failed" in line.summary and "Traceback" not in line.summary
    assert line.posture.updated_at == wf.updated_at and line.posture.kind is None


async def test_execution_uses_parent_id_and_never_raw_error():
    wf = _workflow()
    ex = _failed_run(wf)
    store = AsyncMock()
    store.get_execution = AsyncMock(return_value=ex)
    ref = ScreenRef(
        kind="workflow_execution",
        id=str(ex.id),
        parent_id=str(wf.id),
        label="Run of Oct 16",
    )
    [line] = await WorkflowScreenResolver(store).resolve([ref], CTX)
    store.get_execution.assert_awaited_once_with(wf.id, ex.id)
    assert line.label == "Run of Oct 16"
    assert "failed, 2 of 4 steps, 41 s" in line.summary
    assert "Traceback" not in line.summary and "secret" not in line.summary


async def test_execution_without_parent_is_failed_not_missing():
    store = AsyncMock()
    [line] = await WorkflowScreenResolver(store).resolve(
        [ScreenRef(kind="workflow_execution", id=str(uuid4()))], CTX
    )
    assert line.status is ScreenStatus.FAILED and line.summary == "missing parent"
    store.get_execution.assert_not_called()


async def test_execution_missing_when_the_store_has_no_row():
    store = AsyncMock()
    store.get_execution = AsyncMock(return_value=None)
    ref = ScreenRef(kind="workflow_execution", id=str(uuid4()), parent_id=str(uuid4()))
    [line] = await WorkflowScreenResolver(store).resolve([ref], CTX)
    assert line.status is ScreenStatus.MISSING


async def test_held_write_line_names_the_first_item():
    hold = HeldWrite(
        request_id="req-1",
        source="workflow",
        owner_ref="e1",
        items=[
            {"effect_phrase": "send an email", "summary": "Reply to Ana"},
            {"effect_phrase": "x", "summary": "y"},
        ],
        expires_at=NOW + timedelta(hours=20),
        created_at=NOW - timedelta(hours=4),
    )
    store = AsyncMock()
    store.get = AsyncMock(return_value=hold)
    [line] = await HeldWriteScreenResolver(store).resolve(
        [ScreenRef(kind="held_write", id="req-1")], CTX
    )
    assert "send an email: Reply to Ana" in line.summary
    assert "2 items" in line.summary and "expires in 20 h" in line.summary
    assert "from workflow run" in line.summary


def test_factory_registers_every_kind_once():
    resolvers = build_screen_resolvers(
        goal_store=AsyncMock(), workflow_store=AsyncMock(), held_write_store=AsyncMock()
    )
    kinds = [k for r in resolvers for k in r.kinds]
    assert sorted(kinds) == sorted(
        {"goal", "goal_gate", "workflow", "workflow_execution", "held_write"}
    )
