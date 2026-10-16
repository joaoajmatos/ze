from __future__ import annotations

import asyncio
import html as _html
from collections.abc import Awaitable, Callable

from ze_agents.interface.types import Action
from ze_automation.goals.planner import GoalPlanner
from ze_automation.goals.store import GoalStore
from ze_automation.goals.types import Goal, GoalStatus, Milestone, VerificationGate
from ze_automation.push_kinds import GOAL_OVERLAP, GOAL_PLAN_PROPOSED
from ze_logging import get_logger
from ze_proactive.notifier import ProactiveNotifier

log = get_logger(__name__)


async def plan_for_goal(
    store: GoalStore, planner: GoalPlanner, goal: Goal
) -> tuple[list[Milestone], list[VerificationGate]]:
    """Plan a goal with recent milestone output as context. Raises GoalPlanError."""
    try:
        prior_work = await store.list_completed_milestone_summaries(
            days=90,
            limit=20,
            exclude_goal_id=None,
        )
    except Exception as exc:
        log.warning("goal_prior_work_query_failed", error=str(exc))
        prior_work = []
    return await planner.plan(goal, prior_work=prior_work or None)


async def propose_goal(
    store: GoalStore,
    planner: GoalPlanner,
    notifier: ProactiveNotifier,
    goal: Goal,
    milestones: list[Milestone],
    gates: list[VerificationGate],
    *,
    active_goals: list[Goal],
    claim: Callable[[Goal], Awaitable[bool]] | None = None,
    release: Callable[[Goal], Awaitable[object]] | None = None,
) -> Goal | None:
    """Persist a planned goal and send the plan for approval.

    `claim` runs once the goal row exists and before the plan is stored or sent.
    When it returns False the goal is abandoned and nothing is proposed.
    If the claim, storing the plan, or sending it fails (or the task is
    cancelled), the goal is abandoned, `release` undoes the claim, and the
    original error is raised.
    """
    goal = await store.create_goal(goal)
    try:
        if claim is not None and not await claim(goal):
            await store.update_status(goal.id, GoalStatus.ABANDONED)
            return None
        await _store_and_send_plan(store, notifier, goal, milestones, gates)
    except BaseException:
        # Shielded so a cancelled turn still abandons the goal and reopens the claim.
        await asyncio.shield(_undo_proposal(store, goal, release))
        raise

    asyncio.create_task(
        _check_convergence(store, planner, notifier, goal, active_goals)
    )
    return goal


async def _undo_proposal(
    store: GoalStore,
    goal: Goal,
    release: Callable[[Goal], Awaitable[object]] | None,
) -> None:
    try:
        await store.update_status(goal.id, GoalStatus.ABANDONED)
    except Exception as exc:
        log.error("goal_proposal_abandon_failed", goal_id=str(goal.id), error=str(exc))
    if release is None:
        return
    try:
        await release(goal)
    except Exception as exc:
        log.error("goal_proposal_release_failed", goal_id=str(goal.id), error=str(exc))


async def _store_and_send_plan(
    store: GoalStore,
    notifier: ProactiveNotifier,
    goal: Goal,
    milestones: list[Milestone],
    gates: list[VerificationGate],
) -> None:
    for m in milestones:
        m.goal_id = goal.id
    for g in gates:
        g.goal_id = goal.id

    for m in milestones:
        await store.create_milestone(m)
    for g in gates:
        await store.create_gate(g)

    step_summary = "\n".join(f"  {m.sequence}. {m.title}" for m in milestones)
    gate_summary = (
        "\n".join(f"  Gate after step {g.after_sequence}: {g.title}" for g in gates)
        or "  (none)"
    )

    plan_text = (
        f"🎯 <b>{_html.escape(goal.title)}</b> — proposed plan\n\n"
        f"<b>Milestones:</b>\n{_html.escape(step_summary)}\n\n"
        f"<b>Checkpoints:</b>\n{_html.escape(gate_summary)}\n\n"
        "Start this goal?"
    )
    await notifier.notify(
        GOAL_PLAN_PROPOSED,
        "Goal plan ready",
        plan_text,
        format="html",
        actions=(
            Action(label="Start goal", payload=f"goal_plan:yes:{goal.id}"),
            Action(label="Cancel", payload=f"goal_plan:no:{goal.id}"),
        ),
        target_type="goal",
        target_id=str(goal.id),
    )


async def _check_convergence(
    store: GoalStore,
    planner: GoalPlanner,
    notifier: ProactiveNotifier,
    new_goal: Goal,
    active_goals: list[Goal],
) -> None:
    others = [g for g in active_goals if g.id != new_goal.id]
    if not others:
        return
    try:
        conv = await planner.detect_convergence(new_goal, others)
    except Exception as exc:
        log.warning("goal_convergence_check_failed", error=str(exc))
        return
    if conv is None:
        return
    log.info(
        "goal_convergence_detected",
        new_goal_id=str(new_goal.id),
        overlapping_goal_id=str(conv.overlapping_goal_id),
    )
    await notifier.notify(
        GOAL_OVERLAP,
        "Goal overlap detected",
        f"<b>Goal overlap detected</b>\n\n"
        f"<b>{_html.escape(new_goal.title)}</b> and "
        f"<b>{_html.escape(conv.overlapping_goal_title)}</b> share scope: "
        f"{_html.escape(conv.overlap_description)}\n\n"
        f"Suggested approach: <i>{_html.escape(conv.suggestion)}</i>. "
        f"Let me know if you'd like to share outputs between them, sequence one "
        f"after the other, or keep them running independently.",
        format="html",
        target_type="goal",
        target_id=str(new_goal.id),
        budget_key=f"goal_overlap:{new_goal.id}",
    )
