"""FR-007 / SC-002: a cooldown job starts its window only after a push that was sent.

Each job runs against a real `ProactiveNotifier` over `InMemoryPushLog` and a fake
interface whose first push raises. Only the stores are mocks.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from ze_automation.bootstrap import make_workflow_failure_handler
from ze_automation.goals.types import (
    Goal,
    GoalStatus,
    Milestone,
    MilestoneStatus,
)
from ze_automation.jobs.accountability import AccountabilityJob
from ze_automation.jobs.goal_narrative import GoalNarrativeJob
from ze_automation.workflow.types import StepResult, WorkflowExecution, WorkflowStep
from ze_personal.jobs.briefing import MorningBriefing
from ze_proactive.notifier import ProactiveNotifier
from ze_proactive.testing import InMemoryPushLog
from ze_proactive.types import NotificationRow, OncePer, QuietHoursSetting

NOON = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
NIGHT = datetime(2026, 6, 15, 2, 0, tzinfo=timezone.utc)
QUIET = QuietHoursSetting(True, time(23), time(8), "UTC", None)


class Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def _row(**kw):
    d = dict(
        id="n-1",
        event_type="x",
        source="tests",
        title="T",
        body="B",
        target_type=None,
        target_id=None,
        target_parent_id=None,
        created_at=NOON,
        read_at=None,
        push_class="accountability",
        urgency="normal",
        format="text",
        actions=[],
        delivery="delivered",
        delivered_at=None,
    )
    d.update(kw)
    return NotificationRow(**d)


@dataclass
class Rig:
    run: Callable[[], Awaitable[None]]
    builder: AsyncMock | MagicMock | None
    once_per: OncePer


def _notifier(clock: Clock, log: InMemoryPushLog, *, quiet: bool):
    interface = AsyncMock()
    interface.push = AsyncMock(side_effect=[RuntimeError("boom"), None, None, None])
    store = AsyncMock()
    store.create = AsyncMock(side_effect=lambda **kw: _row(**kw))
    settings = None
    if quiet:
        settings = MagicMock()
        settings.get = AsyncMock(return_value=QUIET)
    notifier = ProactiveNotifier(
        interface,
        store,
        push_log=log,
        settings_store=settings,
        max_discretionary_per_day=5,
        clock=clock,
    )
    return notifier, interface


def _accountability(notifier: ProactiveNotifier) -> Rig:
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value={"total_cost": 0})
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=cm)
    goal_store = AsyncMock()
    goal_store.list_active = AsyncMock(return_value=[])
    workflow_store = AsyncMock()
    workflow_store.list_failed_executions = AsyncMock(return_value=[])
    acc_store = AsyncMock()
    acc_store.list_anomalies_since = AsyncMock(return_value=[])
    job = AccountabilityJob(
        notifier=notifier,
        workflow_store=workflow_store,
        accountability_store=acc_store,
        goal_store=goal_store,
        pool=pool,
    )
    return Rig(
        job.run,
        pool.acquire,
        OncePer("weekly_accountability", within=timedelta(days=6)),
    )


def _goal_narrative(notifier: ProactiveNotifier) -> Rig:
    goal = Goal(
        id=uuid4(),
        title="Ship it",
        objective="o",
        success_condition="s",
        status=GoalStatus.ACTIVE,
    )
    done = Milestone(
        id=uuid4(),
        goal_id=goal.id,
        title="Step 1",
        description="d",
        sequence=1,
        status=MilestoneStatus.COMPLETED,
    )
    done.completed_at = datetime.now(timezone.utc)
    goal_store = AsyncMock()
    goal_store.list_active = AsyncMock(return_value=[goal])
    goal_store.list_milestones = AsyncMock(return_value=[done])
    goal_store.get_pending_gate = AsyncMock(return_value=None)
    planner = AsyncMock()
    planner.synthesize_weekly_narrative = AsyncMock(return_value="Progress.")
    job = GoalNarrativeJob(
        notifier=notifier, goal_store=goal_store, goal_planner=planner
    )
    return Rig(
        job.run,
        planner.synthesize_weekly_narrative,
        OncePer("goal_narrative", within=timedelta(hours=144)),
    )


def _briefing(notifier: ProactiveNotifier) -> Rig:
    memory = MagicMock()
    memory.count_unreviewed_facts = AsyncMock(return_value=0)
    workflow_store = MagicMock()
    workflow_store.list_enabled_scheduled = AsyncMock(return_value=[])
    workflow_store.list_failed_executions = AsyncMock(return_value=[])
    priority_view = MagicMock()
    priority_view.rank = AsyncMock(return_value=SimpleNamespace(items=[]))
    news = MagicMock()
    news.get_recent = AsyncMock(return_value=[])
    news.get_personalized = AsyncMock(return_value=([], []))
    settings = SimpleNamespace(config={"news": {"personalization": {"enabled": False}}})
    job = MorningBriefing(
        notifier=notifier,
        memory_store=memory,
        workflow_store=workflow_store,
        settings=settings,
        priority_view=priority_view,
        news_store=news,
    )
    return Rig(
        job.run, news.get_recent, OncePer("morning_brief", within=timedelta(hours=20))
    )


def _workflow_failure(notifier: ProactiveNotifier) -> Rig:
    workflow = SimpleNamespace(id=uuid4(), name="Weekly invoices")
    execution = WorkflowExecution(
        id=uuid4(),
        workflow_id=workflow.id,
        status="failed",
        step_results=[StepResult(0, "Check", "", False, "TimeoutError: boom", 5)],
        steps_snapshot=[WorkflowStep(task="Check")],
        error="TimeoutError: boom",
        created_at=datetime.now(timezone.utc),
    )
    store = AsyncMock()
    store.list_executions = AsyncMock(return_value=[execution])
    handler = make_workflow_failure_handler(
        settings=SimpleNamespace(proactive_config={}),
        workflow_store=store,
        notifier=notifier,
    )

    async def run() -> None:
        await handler(workflow, RuntimeError("boom"))

    return Rig(
        run,
        None,
        OncePer(f"workflow_failure_alert:{workflow.id}", within=timedelta(hours=1)),
    )


RIGS = {
    "accountability": _accountability,
    "goal_narrative": _goal_narrative,
    "morning_briefing": _briefing,
    "workflow_failure": _workflow_failure,
}


def _setup(name: str, *, now: datetime = NOON, quiet: bool = False):
    clock = Clock(now)
    log = InMemoryPushLog(clock)
    notifier, interface = _notifier(clock, log, quiet=quiet)
    return RIGS[name](notifier), interface, log, clock


@pytest.mark.parametrize("name", RIGS)
async def test_a_failed_push_starts_no_cooldown(name):
    rig, interface, log, clock = _setup(name)

    await rig.run()
    assert interface.push.await_count == 1
    assert log.rows == []

    await rig.run()
    assert interface.push.await_count == 2
    assert [r.claim_key for r in log.rows] == [rig.once_per.key]

    clock.now = NOON + timedelta(minutes=5)
    await rig.run()
    assert interface.push.await_count == 2


@pytest.mark.parametrize("name", RIGS)
async def test_a_held_push_starts_the_cooldown(name):
    rig, interface, log, clock = _setup(name, now=NIGHT, quiet=True)

    await rig.run()
    assert [r.claim_key for r in log.rows] == [rig.once_per.key]
    after_first = interface.push.await_count

    clock.now = NIGHT + timedelta(minutes=5)
    await rig.run()
    assert interface.push.await_count == after_first
    assert len(log.rows) == 1


@pytest.mark.parametrize("name", RIGS)
async def test_the_window_ends_with_its_duration(name):
    rig, interface, log, clock = _setup(name)
    interface.push = AsyncMock()

    await rig.run()
    await rig.run()
    assert interface.push.await_count == 1

    clock.now = NOON + rig.once_per.within + timedelta(minutes=1)
    await rig.run()
    assert interface.push.await_count == 2


@pytest.mark.parametrize("name", RIGS)
async def test_a_cooling_job_does_not_build_its_message(name):
    rig, interface, log, _ = _setup(name)
    interface.push = AsyncMock()
    await log.claim(
        event_type="seed",
        once_per=rig.once_per,
        discretionary=False,
        max_discretionary=5,
        payload=None,
    )

    await rig.run()

    interface.push.assert_not_awaited()
    if rig.builder is not None:
        rig.builder.assert_not_called()
