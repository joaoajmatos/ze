"""Real-Postgres paths of unattended write holds (Phase 181, US5)."""

import uuid
from datetime import timedelta

import asyncpg
import pytest
import pytest_asyncio
from ze_agents.park import ParkedLoop, ParkedWrite
from ze_agents.types import ToolCall
from ze_automation.goals.postgres import PostgresGoalStore
from ze_automation.goals.types import Goal, Milestone, MilestoneStatus
from ze_automation.holds.serialize import loop_from_dict, loop_to_dict
from ze_automation.holds.store import PostgresHeldWriteStore
from ze_automation.holds.types import HeldWrite
from ze_automation.workflow.postgres import PostgresWorkflowStore
from ze_automation.workflow.types import Workflow, WorkflowStep

from ze_api.db import _init_conn
from tests.pg._builders import utcnow

pytestmark = pytest.mark.pg


@pytest_asyncio.fixture
async def prod_pool(pg_dsn):
    """A pool set up like production: jsonb values are encoded and decoded as JSON."""
    pool = await asyncpg.create_pool(pg_dsn, min_size=1, max_size=4, init=_init_conn)
    yield pool
    await pool.close()


def _workflow() -> Workflow:
    now = utcnow()
    return Workflow(
        id=None,  # type: ignore[arg-type]
        name=f"wf-{uuid.uuid4().hex[:8]}",
        description="d",
        steps=[
            WorkflowStep(task="gather", id="s0"),
            WorkflowStep(
                task="send",
                id="s1",
                agent_hint="messenger",
                planned_writes=["send_email"],
                approved_writes=["send_email"],
            ),
        ],
        schedule=None,
        enabled=True,
        last_run_at=None,
        next_run_at=None,
        created_at=now,
        updated_at=now,
    )


async def test_workflow_step_approved_writes_round_trip(prod_pool):
    store = PostgresWorkflowStore(db_pool=prod_pool)
    wf_id = await store.create(_workflow())

    loaded = await store.get(wf_id)

    assert [s.approved_writes for s in loaded.steps] == [[], ["send_email"]]
    assert [s.planned_writes for s in loaded.steps] == [[], ["send_email"]]


async def test_execution_can_be_held_and_resumed_only_from_held(prod_pool):
    store = PostgresWorkflowStore(db_pool=prod_pool)
    wf_id = await store.create(_workflow())
    execution_id = await store.start_execution(wf_id)

    assert await store.set_execution_status(execution_id, "held") is True
    execution = await store.get_execution(wf_id, execution_id)
    assert execution.status == "held" and execution.completed_at is None

    assert await store.set_execution_status(execution_id, "running", expected="held")
    assert not await store.set_execution_status(
        execution_id, "running", expected="held"
    )
    assert await store.recover_stale(timeout_minutes=0) >= 0


async def test_milestone_approved_writes_and_held_status_persist(prod_pool):
    store = PostgresGoalStore(pool=prod_pool)
    goal = await store.create_goal(
        Goal(title="Outreach", objective="o", success_condition="s")
    )
    created = await store.create_milestone(
        Milestone(
            goal_id=goal.id,
            title="Email the lead",
            description="send it",
            sequence=1,
            agent_hint="messenger",
            approved_writes=["send_email", "archive_email"],
        )
    )
    assert created.approved_writes == ["send_email", "archive_email"]

    await store.update_milestone(created.id, MilestoneStatus.HELD)
    milestones = await store.list_milestones(goal.id)

    assert milestones[0].status is MilestoneStatus.HELD
    assert milestones[0].approved_writes == ["send_email", "archive_email"]


async def test_held_goal_payload_round_trips_a_parked_loop_through_jsonb(prod_pool):
    loop = ParkedLoop(
        agent="messenger",
        messages=[{"role": "assistant", "content": None, "tool_calls": []}],
        accumulated=[
            ToolCall(
                tool_name="list_mail",
                args={"q": "x"},
                result={"n": 2},
                duration_ms=3,
                success=True,
            )
        ],
        iteration=1,
        parked=[
            ParkedWrite(
                item_id="i1",
                call_id="c1",
                tool="send_email",
                args={"to": "a@b.io"},
                effect_phrase="sent an email",
                summary="to: a@b.io",
                agent="messenger",
                editable_field="body",
            )
        ],
    )
    store = PostgresHeldWriteStore(prod_pool)
    hold = HeldWrite(
        request_id=f"req-{uuid.uuid4().hex}",
        source="goal",
        owner_ref=str(uuid.uuid4()),
        items=[{"item_id": "i1"}],
        payload={"loop": loop_to_dict(loop), "round": 1},
        expires_at=utcnow() + timedelta(hours=24),
    )
    await store.create(hold)

    loaded = await store.get(hold.request_id)
    restored = loop_from_dict(loaded.payload["loop"])

    assert restored.agent == "messenger"
    assert restored.parked[0].tool == "send_email"
    assert restored.parked[0].args == {"to": "a@b.io"}
    assert restored.accumulated[0].tool_name == "list_mail"
    assert restored.iteration == 1
