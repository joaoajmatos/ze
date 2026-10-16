from __future__ import annotations

import asyncio
from uuid import UUID

from ze_agents.tool import AskDecision, ToolAccess, tool, undo_payload
from ze_agents.reversibility import ToolReversibility
from ze_agents.errors import GoalPlanError
from ze_automation.goals.executor import GoalExecutor
from ze_automation.holds.planned import (
    approval_given,
    grant_planned_writes,
    memo_of,
    plan_writes_check,
)
from ze_automation.goals.planner import GoalPlanner
from ze_automation.goals.postgres import PostgresGoalStore as GoalStore
from ze_automation.goals.proposal import plan_for_goal, propose_goal
from ze_automation.goals.types import (
    Goal,
    GoalStatus,
    Milestone,
    MilestoneStatus,
    VerificationGate,
)
from ze_logging import get_logger
from ze_sdk.proactive import ProactiveNotifier

log = get_logger(__name__)


@tool(
    access=ToolAccess.WRITE,
    description="Redirect a running goal with new instructions. Ze will finish its current step and then replan the remaining milestones incorporating your direction.",
    reversibility=ToolReversibility.IRREVERSIBLE,
    effect_phrase="steered a goal",
    asks_first=False,
    no_ask_reason="Queues the user's own instruction for the goal; the next milestone reads it.",
)
async def steer_goal(executor: GoalExecutor, goal_id: str, instruction: str) -> str:
    try:
        uid = UUID(goal_id)
    except ValueError:
        return f"Invalid goal ID: {goal_id!r}"
    ok = await executor.steer(uid, instruction)
    if not ok:
        return "That goal is not currently active. Use list_goals to check status."
    return "Got it — I'll apply that direction after the current step finishes."


@tool(access=ToolAccess.READ, description="List all goals with their current status.")
async def list_goals(store: GoalStore) -> list:
    goals = await store.list_all()
    return [
        {
            "id": str(g.id),
            "title": g.title,
            "status": g.status.value,
            "objective": g.objective[:120],
            "type": g.type,
        }
        for g in goals
    ]


@tool(
    access=ToolAccess.READ,
    description="Get full status of a goal by its ID, including milestones and pending gate.",
)
async def get_goal_status(store: GoalStore, goal_id: str) -> dict:
    try:
        uid = UUID(goal_id)
    except ValueError:
        return {"error": f"Invalid goal ID: {goal_id!r}"}

    goal = await store.get_goal(uid)
    if not goal:
        return {"error": f"Goal not found: {goal_id}"}

    milestones = await store.list_milestones(uid)
    gate = await store.get_pending_gate(uid)

    completed = sum(1 for m in milestones if m.status == MilestoneStatus.COMPLETED)
    skipped = sum(1 for m in milestones if m.status.value == "skipped")
    total = len(milestones)

    result: dict = {
        "id": str(goal.id),
        "title": goal.title,
        "status": goal.status.value,
        "objective": goal.objective,
        "progress": f"{completed}/{total} milestones done"
        + (f" ({skipped} skipped)" if skipped else ""),
        "milestones": [
            {"sequence": m.sequence, "title": m.title, "status": m.status.value}
            for m in milestones
        ],
        "pending_gate": (
            {
                "gate_id": str(gate.id),
                "title": gate.title,
                "context_summary": gate.context_summary,
                "plan_summary": gate.plan_summary,
            }
            if gate
            else None
        ),
    }
    eligible = await store.list_eligible_learnings("", goal_id=goal.id, limit=5)
    if eligible:
        result["learnings"] = [
            f"[{item.claim_kind.value}] {item.content}" for item in eligible
        ]
    return result


def _new_goal(
    goal_title: str,
    objective: str,
    success_condition: str,
    time_horizon: str,
    goal_type: str,
) -> Goal:
    return Goal(
        title=goal_title,
        objective=objective,
        success_condition=success_condition,
        time_horizon=time_horizon,
        type=goal_type,
        status=GoalStatus.PLANNING,
    )


async def _plan_goal(
    store: GoalStore, planner: GoalPlanner, goal: Goal, *, consume: bool
) -> tuple[list[Milestone], list[VerificationGate], bool]:
    """Plan once: the check shows the plan, the approved call runs that same plan."""
    memo = memo_of(planner)
    key = (
        "goal",
        goal.title,
        goal.objective,
        goal.success_condition,
        goal.time_horizon,
        goal.type,
    )
    if memo is not None:
        shown = memo.take(key) if consume else memo.get(key)
        if shown is not None:
            return shown[0], shown[1], True
    milestones, gates = await plan_for_goal(store, planner, goal)
    if memo is not None and not consume:
        memo.put(key, (milestones, gates))
    return milestones, gates, False


async def create_goal_check(args: dict, ctx) -> AskDecision:
    store = args.get("store")
    planner = args.get("planner")
    if store is None or planner is None:
        return AskDecision.run()
    goal = _new_goal(
        args.get("goal_title", ""),
        args.get("objective", ""),
        args.get("success_condition", ""),
        args.get("time_horizon", ""),
        args.get("goal_type", "custom"),
    )
    try:
        milestones, _, _ = await _plan_goal(store, planner, goal, consume=False)
    except GoalPlanError:
        return AskDecision.run()
    return plan_writes_check(milestones, label="Milestone")


@tool(
    access=ToolAccess.WRITE,
    description="Create a new goal and propose a milestone plan for user approval.",
    reversibility=ToolReversibility.REVERSIBLE,
    undo_tool="abandon_goal",
    undo_note=(
        "Abandoning the goal does not undo work already started. "
        "A notification already sent stays"
    ),
    effect_phrase="created a goal",
    ask_check=create_goal_check,
)
async def create_goal(
    store: GoalStore,
    planner: GoalPlanner,
    notifier: ProactiveNotifier,
    goal_title: str,
    objective: str,
    success_condition: str,
    time_horizon: str = "",
    goal_type: str = "custom",
) -> dict:
    active_goals = await store.list_active()

    goal = _new_goal(goal_title, objective, success_condition, time_horizon, goal_type)

    try:
        milestones, gates, shown = await _plan_goal(store, planner, goal, consume=True)
    except GoalPlanError as exc:
        return {"error": f"Couldn't plan the goal: {exc}"}
    if shown and approval_given():
        grant_planned_writes(milestones)

    goal = await propose_goal(
        store, planner, notifier, goal, milestones, gates, active_goals=active_goals
    )

    return {
        "id": str(goal.id),
        "title": goal_title,
        "milestones": len(milestones),
        "gates": len(gates),
        "undo": undo_payload(goal_id=str(goal.id)),
    }


@tool(
    access=ToolAccess.WRITE,
    description="Pause an active goal by its ID.",
    reversibility=ToolReversibility.REVERSIBLE,
    undo_tool="resume_goal",
    undo_note="Resumes the goal.",
    effect_phrase="paused a goal",
)
async def pause_goal(store: GoalStore, executor: GoalExecutor, goal_id: str) -> dict:
    try:
        uid = UUID(goal_id)
    except ValueError:
        return {"error": f"Invalid goal ID: {goal_id!r}"}
    goal = await store.get_goal(uid)
    if not goal:
        return {"error": f"Goal not found: {goal_id}"}
    await store.update_status(uid, GoalStatus.PAUSED)
    await executor.close_holds(uid)
    return {
        "title": goal.title,
        "status": "paused",
        "undo": undo_payload(goal_id=str(uid)),
    }


@tool(
    access=ToolAccess.WRITE,
    description="Resume a paused goal by its ID and continue execution.",
    reversibility=ToolReversibility.REVERSIBLE,
    undo_tool="pause_goal",
    undo_note="Pauses the goal again.",
    effect_phrase="resumed a goal",
)
async def resume_goal(store: GoalStore, executor: GoalExecutor, goal_id: str) -> dict:
    try:
        uid = UUID(goal_id)
    except ValueError:
        return {"error": f"Invalid goal ID: {goal_id!r}"}
    goal = await store.get_goal(uid)
    if not goal:
        return {"error": f"Goal not found: {goal_id}"}
    if goal.status != GoalStatus.PAUSED:
        return {
            "error": f"Goal '{goal.title}' is not paused (status: {goal.status.value})."
        }
    await store.update_status(uid, GoalStatus.ACTIVE)
    asyncio.create_task(executor.advance(uid))
    return {
        "title": goal.title,
        "status": "active",
        "undo": undo_payload(goal_id=str(uid)),
    }


@tool(
    access=ToolAccess.READ,
    description="Return the execution trace for a specific milestone — what tools Ze called and what they returned.",
)
async def get_milestone_trace(
    store: GoalStore, goal_id: str, milestone_sequence: int
) -> str:
    try:
        uid = UUID(goal_id)
    except ValueError:
        return f"Invalid goal ID: {goal_id!r}"

    milestones = await store.list_milestones(uid)
    target = next((m for m in milestones if m.sequence == milestone_sequence), None)
    if target is None:
        return (
            f"No milestone with sequence {milestone_sequence} found for goal {goal_id}."
        )

    traces = await store.list_traces(goal_id=uid, milestone_id=target.id)
    if not traces:
        return "No execution trace recorded for this milestone."

    lines = [f"Execution trace for milestone {milestone_sequence}: {target.title}\n"]
    for t in traces:
        status = "OK" if t.success else f"FAILED ({t.error})"
        lines.append(f"  [{t.seq}] {t.tool_name} ({t.duration_ms}ms) — {status}")
        if t.args:
            import json as _json

            lines.append(f"       args: {_json.dumps(t.args)[:200]}")
        lines.append(f"       result: {t.result[:300]}")
    return "\n".join(lines)


async def _goal_title(args: dict) -> str | None:
    goal = await args["store"].get_goal(UUID(args["goal_id"]))
    return f'"{goal.title}"' if goal else None


@tool(
    access=ToolAccess.WRITE,
    description="Abandon a goal permanently by its ID.",
    reversibility=ToolReversibility.IRREVERSIBLE,
    effect_phrase="abandoned a goal",
    summarize=_goal_title,
)
async def abandon_goal(store: GoalStore, executor: GoalExecutor, goal_id: str) -> dict:
    try:
        uid = UUID(goal_id)
    except ValueError:
        return {"error": f"Invalid goal ID: {goal_id!r}"}
    goal = await store.get_goal(uid)
    if not goal:
        return {"error": f"Goal not found: {goal_id}"}
    await store.update_status(uid, GoalStatus.ABANDONED)
    await executor.close_holds(uid)
    return {"title": goal.title, "status": "abandoned"}
