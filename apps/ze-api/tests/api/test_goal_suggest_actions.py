"""goal_suggest:accept|dismiss|more:<short id> — the weekly goal suggestion buttons (CF-04, T-01)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from ze_agents.errors import GoalPlanError
from ze_api.api.ws.connection import ConnectionManager
from ze_api.api.ws.goal_actions import handle_action
from ze_automation.goals.types import (
    Goal,
    GoalStatus,
    GoalSuggestion,
    Milestone,
    SuggestionStatus,
    VerificationGate,
)
from ze_automation.push_kinds import GOAL_PLAN_PROPOSED

THREAD = "thread-abc"


def _suggestion(status: SuggestionStatus = SuggestionStatus.PENDING) -> GoalSuggestion:
    return GoalSuggestion(
        id=uuid4(),
        title="Learn Spanish",
        objective="Reach conversational fluency in Spanish within six months.",
        rationale="You mentioned the trip to Lisbon and enjoyed the language retro.",
        source_type="retrospective",
        source_ref="Travel",
        status=status,
        suggested_at=datetime.now(timezone.utc),
    )


class _Rig:
    def __init__(self, suggestion: GoalSuggestion | None) -> None:
        self.suggestion = suggestion
        self.store = AsyncMock()

        async def create_goal(goal: Goal) -> Goal:
            goal.id = uuid4()
            return goal

        self.store.create_goal = AsyncMock(side_effect=create_goal)
        self.store.list_active = AsyncMock(return_value=[])
        self.store.list_completed_milestone_summaries = AsyncMock(return_value=[])
        self.suggestions = AsyncMock()
        self.suggestions.resolve_short_id = AsyncMock(return_value=suggestion)
        self.suggestions.mark_accepted = AsyncMock(return_value=True)
        self.suggestions.mark_dismissed = AsyncMock(return_value=True)
        self.suggestions.reopen = AsyncMock(return_value=True)
        self.planner = AsyncMock()
        self.planner.plan = AsyncMock(
            return_value=(
                [
                    Milestone(
                        goal_id=None, title="Pick a course", description="d", sequence=1
                    )
                ],
                [
                    VerificationGate(
                        goal_id=None, after_sequence=1, title="Course chosen"
                    )
                ],
            )
        )
        self.notifier = AsyncMock()
        self.container = MagicMock()
        self.container._plugin_stores = {
            "goal_store": self.store,
            "goal_executor": AsyncMock(),
            "goal_suggestion_store": self.suggestions,
            "goal_planner": self.planner,
        }
        self.container.notifier = self.notifier
        self.container.interface = AsyncMock()
        self.container.interface.send_with_thread = AsyncMock()
        self.conn = ConnectionManager()
        self.ws = AsyncMock()
        self.ws.send_json = AsyncMock()

    async def act(self, action: str, short_id: str | None = None) -> None:
        await self.conn.connect(self.ws, AsyncMock())
        sid = short_id or (
            self.suggestion.id.hex[:8] if self.suggestion else "deadbeef"
        )
        await handle_action(
            self.ws,
            {"payload": f"goal_suggest:{action}:{sid}", "thread_id": THREAD},
            self.container,
            self.conn,
        )

    @property
    def frames(self) -> list[dict]:
        return [c.args[0] for c in self.ws.send_json.call_args_list]

    @property
    def replies(self) -> list[str]:
        return [
            c.args[0] for c in self.container.interface.send_with_thread.call_args_list
        ]

    @property
    def errors(self) -> list[str]:
        return [f["detail"] for f in self.frames if f.get("type") == "error"]


async def test_accept_plans_the_goal_claims_the_suggestion_and_sends_the_proposal():
    rig = _Rig(_suggestion())

    await rig.act("accept")

    rig.suggestions.resolve_short_id.assert_awaited_once_with(rig.suggestion.id.hex[:8])
    created: Goal = rig.store.create_goal.await_args.args[0]
    assert (created.title, created.type) == ("Learn Spanish", "suggested")
    assert created.status is GoalStatus.PLANNING
    assert created.success_condition == rig.suggestion.objective
    rig.suggestions.mark_accepted.assert_awaited_once_with(
        rig.suggestion.id, created.id
    )
    rig.store.create_milestone.assert_awaited_once()
    rig.store.create_gate.assert_awaited_once()
    args, kwargs = rig.notifier.notify.await_args
    assert args[0] is GOAL_PLAN_PROPOSED
    assert [a.payload for a in kwargs["actions"]] == [
        f"goal_plan:yes:{created.id}",
        f"goal_plan:no:{created.id}",
    ]
    assert any(f.get("type") == "refresh" for f in rig.frames)


async def test_accept_does_not_start_the_goal():
    rig = _Rig(_suggestion())
    executor = rig.container._plugin_stores["goal_executor"]

    await rig.act("accept")

    executor.approve_plan.assert_not_called()


async def test_accept_that_cannot_plan_leaves_the_suggestion_pending():
    rig = _Rig(_suggestion())
    rig.planner.plan = AsyncMock(side_effect=GoalPlanError("no milestones"))

    await rig.act("accept")

    rig.store.create_goal.assert_not_called()
    rig.suggestions.mark_accepted.assert_not_called()
    rig.notifier.notify.assert_not_called()
    assert any("plan" in r.lower() for r in rig.replies + rig.errors)


async def test_accept_that_loses_the_race_abandons_the_stray_goal_and_proposes_nothing():
    rig = _Rig(_suggestion())
    rig.suggestions.mark_accepted = AsyncMock(return_value=False)

    await rig.act("accept")

    created: Goal = rig.store.create_goal.await_args.args[0]
    rig.store.update_status.assert_awaited_once_with(created.id, GoalStatus.ABANDONED)
    rig.store.create_milestone.assert_not_called()
    rig.notifier.notify.assert_not_called()
    assert any("already" in e.lower() for e in rig.errors)


async def test_accept_whose_plan_cannot_be_stored_reopens_the_suggestion_and_says_so():
    rig = _Rig(_suggestion())
    rig.store.create_milestone = AsyncMock(side_effect=RuntimeError("db down"))

    await rig.act("accept")

    created: Goal = rig.store.create_goal.await_args.args[0]
    rig.suggestions.mark_accepted.assert_awaited_once_with(
        rig.suggestion.id, created.id
    )
    rig.store.update_status.assert_awaited_once_with(created.id, GoalStatus.ABANDONED)
    rig.suggestions.reopen.assert_awaited_once_with(rig.suggestion.id, created.id)
    rig.notifier.notify.assert_not_called()
    assert not any(f.get("type") == "refresh" for f in rig.frames)
    (reply,) = rig.replies
    assert "Learn Spanish" in reply and "try again" in reply
    assert rig.errors == []


async def test_accept_on_a_resolved_suggestion_plans_nothing():
    rig = _Rig(_suggestion(SuggestionStatus.DISMISSED))

    await rig.act("accept")

    rig.planner.plan.assert_not_called()
    rig.store.create_goal.assert_not_called()
    assert any("already" in e.lower() for e in rig.errors)


async def test_unknown_short_id_is_reported():
    rig = _Rig(None)

    await rig.act("accept")

    rig.store.create_goal.assert_not_called()
    assert any("not found" in e.lower() for e in rig.errors)


async def test_dismiss_records_the_dismissal_and_creates_no_goal():
    rig = _Rig(_suggestion())

    await rig.act("dismiss")

    rig.suggestions.mark_dismissed.assert_awaited_once_with(rig.suggestion.id)
    rig.store.create_goal.assert_not_called()
    assert any("Learn Spanish" in r for r in rig.replies)


async def test_dismiss_on_a_resolved_suggestion_is_reported():
    rig = _Rig(_suggestion())
    rig.suggestions.mark_dismissed = AsyncMock(return_value=False)

    await rig.act("dismiss")

    assert any("already" in e.lower() for e in rig.errors)


async def test_more_repeats_the_rationale_with_the_same_three_buttons():
    suggestion = _suggestion()
    rig = _Rig(suggestion)

    await rig.act("more")

    rig.suggestions.mark_accepted.assert_not_called()
    rig.suggestions.mark_dismissed.assert_not_called()
    (frame,) = [f for f in rig.frames if f.get("type") == "confirm_request"]
    assert suggestion.rationale in frame["title"]
    short = suggestion.id.hex[:8]
    assert [a["value"] for a in frame["actions"]] == [
        f"goal_suggest:accept:{short}",
        f"goal_suggest:dismiss:{short}",
        f"goal_suggest:more:{short}",
    ]


async def test_more_on_a_resolved_suggestion_offers_no_buttons():
    rig = _Rig(_suggestion(SuggestionStatus.ACCEPTED))

    await rig.act("more")

    assert not [f for f in rig.frames if f.get("type") == "confirm_request"]
    assert any("already" in e.lower() for e in rig.errors)


async def test_an_unknown_suggestion_action_is_rejected():
    rig = _Rig(_suggestion())

    await rig.act("explode")

    assert rig.errors == ["Unrecognised action."]
