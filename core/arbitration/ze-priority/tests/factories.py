from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from ze_agents.claims import ClaimKind
from ze_automation.goals.types import Goal, GoalStatus, StuckGoal
from ze_correlation.types import Hypothesis
from ze_worldstate.types import LoopClaimKind, LoopProvenance, LoopState, OpenLoop

UTC = timezone.utc


def make_loop(**overrides) -> OpenLoop:
    base = dict(
        id=uuid4(),
        title="Follow up with Maria",
        claim_kind=LoopClaimKind.PRIORITY,
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
