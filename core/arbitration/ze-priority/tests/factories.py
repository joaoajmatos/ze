from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from ze_agents.claims import ClaimKind
from ze_automation.goals.types import Goal, GoalStatus, StuckGoal
from ze_correlation.types import Hypothesis
from ze_worldstate.types import LoopProvenance, LoopState, OpenLoop

UTC = timezone.utc


def make_loop(**overrides) -> OpenLoop:
    base = dict(
        id=uuid4(),
        title="Follow up with Maria",
        provenance=LoopProvenance.USER_DECLARED,
        confidence=0.5,
        state=LoopState.DRIFTING,
        drift_rationale="No corroborating evidence since last check-in.",
        created_at=datetime.now(UTC) - timedelta(days=10),
        updated_at=datetime.now(UTC) - timedelta(days=10),
    )
    base.update(overrides)
    return OpenLoop(**base)


def make_stuck_goal(**overrides) -> StuckGoal:
    goal_overrides = overrides.pop("goal_overrides", {})
    goal_base = dict(
        id=uuid4(),
        title="Ship the quarterly report",
        objective="Deliver the Q3 report",
        success_condition="Report sent to stakeholders",
        status=GoalStatus.ACTIVE,
        created_at=datetime.now(UTC) - timedelta(days=20),
    )
    goal_base.update(goal_overrides)
    goal = Goal(**goal_base)

    base = dict(
        goal=goal,
        kind="active",
        idle_days=5,
        last_milestone_title="Draft outline",
        gate=None,
    )
    base.update(overrides)
    return StuckGoal(**base)


def make_hypothesis(**overrides) -> Hypothesis:
    base = dict(
        id=uuid4(),
        summary="Ze noticed a connection between two threads",
        narrative="Uncertain, but two recent signals point the same way.",
        relation="pattern",
        confidence=0.4,
        relevance=0.6,
        evidence=[],
        entities=[],
        created_at=datetime.now(UTC) - timedelta(hours=3),
        claim_kind=ClaimKind.INFERENCE,
    )
    base.update(overrides)
    return Hypothesis(**base)


def make_goal_progress(**overrides):
    from ze_automation.goals.types import GoalProgress

    goal_overrides = overrides.pop("goal_overrides", {})
    goal_base = dict(
        id=uuid4(),
        title="Ship the quarterly report",
        objective="Deliver the Q3 report",
        success_condition="Report sent to stakeholders",
        status=GoalStatus.ACTIVE,
        created_at=datetime.now(UTC) - timedelta(days=20),
    )
    goal_base.update(goal_overrides)
    base = dict(
        goal=Goal(**goal_base),
        milestones_done=2,
        milestones_total=5,
        next_milestone="Draft outline",
        gate_id=None,
        gate_title=None,
        gate_open_since=None,
        last_progress_at=None,
        stuck_since=None,
    )
    base.update(overrides)
    return GoalProgress(**base)


def make_held_write(**overrides):
    from ze_automation.holds.types import HeldWrite

    base = dict(
        request_id=str(uuid4()),
        source="workflow",
        owner_ref=str(uuid4()),
        items=[{"effect_phrase": "Send the email", "summary": "Invoice to Ana"}],
        payload={"source_name": "Weekly invoices"},
        expires_at=datetime.now(UTC) + timedelta(hours=20),
        created_at=datetime.now(UTC) - timedelta(hours=4),
    )
    base.update(overrides)
    return HeldWrite(**base)
