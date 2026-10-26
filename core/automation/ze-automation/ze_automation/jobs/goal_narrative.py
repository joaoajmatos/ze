from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ze_logging import get_logger
from ze_proactive.job import proactive_job
from ze_proactive.notifier import ProactiveNotifier
from ze_proactive.types import OncePer
from ze_automation.goals.planner import GoalPlanner
from ze_automation.goals.store import GoalStore
from ze_automation.goals.types import GoalStatus, MilestoneStatus
from ze_automation.push_kinds import GOAL_NARRATIVE

log = get_logger(__name__)

_ONCE_PER = OncePer("goal_narrative", within=timedelta(hours=144))


@proactive_job
class GoalNarrativeJob:
    job_id = "goal_narrative"

    def __init__(
        self,
        notifier: ProactiveNotifier,
        goal_store: GoalStore,
        goal_planner: GoalPlanner,
    ) -> None:
        self._notifier = notifier
        self._store = goal_store
        self._planner = goal_planner

    async def run(self) -> None:
        if await self._notifier.on_cooldown(_ONCE_PER):
            log.info("goal_narrative_skipped_cooldown")
            return

        active_goals = await self._store.list_active()
        if not active_goals:
            log.info("goal_narrative_skipped_no_goals")
            return

        since = datetime.now(timezone.utc) - timedelta(days=7)
        paragraphs: list[str] = []

        for goal in active_goals:
            try:
                milestones = await self._store.list_milestones(goal.id)
                completed_this_week = [
                    m
                    for m in milestones
                    if m.status == MilestoneStatus.COMPLETED
                    and m.completed_at is not None
                    and m.completed_at >= since
                ]
                pending_gate = (
                    await self._store.get_pending_gate(goal.id)
                    if goal.status == GoalStatus.AWAITING_GATE
                    else None
                )
                next_milestones = [
                    m for m in milestones if m.status == MilestoneStatus.PENDING
                ]

                if not completed_this_week and pending_gate is None:
                    continue

                paragraph = await self._planner.synthesize_weekly_narrative(
                    goal, completed_this_week, pending_gate, next_milestones
                )
                header = f"<b>{goal.title}</b>"
                if pending_gate is not None:
                    header += f" ⚠️ awaiting gate: {pending_gate.title}"
                paragraphs.append(f"{header}\n{paragraph}")
            except Exception as exc:
                log.warning(
                    "goal_narrative_goal_failed", goal_id=str(goal.id), error=str(exc)
                )

        if not paragraphs:
            log.info("goal_narrative_nothing_to_report")
            return

        body = "\n\n".join(paragraphs)
        outcome = await self._notifier.notify(
            GOAL_NARRATIVE,
            "Goal progress this week",
            body,
            once_per=_ONCE_PER,
            format="html",
        )
        log.info("goal_narrative_finished", outcome=outcome, goals=len(paragraphs))
