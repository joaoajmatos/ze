from __future__ import annotations

import asyncio
import html as _html
from collections import defaultdict
from typing import Callable
from uuid import UUID

from ze_core.errors import GoalExecutionError
from ze_personal.goals.planner import GoalPlanner
from ze_personal.goals.store import GoalStore
from ze_personal.goals.types import (
    Goal,
    GoalLearning,
    GoalStatus,
    GateStatus,
    Milestone,
    MilestoneStatus,
)
from ze_core.interface.types import Action, Notification
from ze_core.logging import get_logger

log = get_logger(__name__)

_DONE_MILESTONE_STATUSES = frozenset({MilestoneStatus.COMPLETED, MilestoneStatus.SKIPPED})

# Payload format: "goal:<action>:<gate_id>"
# Transport layers parse this in their callback handler and call the appropriate
# GoalExecutor method (handle_gate_approved, handle_gate_stopped, handle_gate_redirected).
_PAYLOAD_APPROVE   = "goal:approve:{gate_id}"
_PAYLOAD_STOP      = "goal:stop:{gate_id}"
_PAYLOAD_REDIRECT  = "goal:redirect:{gate_id}"


class GoalExecutor:
    def __init__(
        self,
        goal_store: GoalStore,
        goal_planner: GoalPlanner,
        push: Callable[[Notification], None],
        agent_getter: Callable[[str], object],
    ) -> None:
        """
        Args:
            goal_store:   GoalStore implementation.
            goal_planner: GoalPlanner for decomposition and replanning.
            push:         Async callable that delivers a Notification to the user.
                          Corresponds to AppInterface.push() — must not raise.
            agent_getter: Callable that looks up a registered agent by name.
                          Returns an object with an async run(ctx) method.
        """
        self._store = goal_store
        self._planner = goal_planner
        self._push = push
        self._get_agent = agent_getter
        self._advance_locks: dict[UUID, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def advance(self, goal_id: UUID) -> None:
        """Advance execution of a goal by one step. Serialized per goal_id."""
        async with self._advance_locks[goal_id]:
            await self._advance_unlocked(goal_id)

    async def _advance_unlocked(self, goal_id: UUID) -> None:
        goal = await self._store.get_goal(goal_id)
        if goal is None or goal.status != GoalStatus.ACTIVE:
            return

        milestones = await self._store.list_milestones(goal_id)
        for stuck in [m for m in milestones if m.status == MilestoneStatus.IN_PROGRESS]:
            log.warning(
                "milestone_in_progress_reset",
                goal_id=str(goal_id),
                milestone_id=str(stuck.id),
                sequence=stuck.sequence,
            )
            await self._store.update_milestone(stuck.id, MilestoneStatus.PENDING)

        milestones = await self._store.list_milestones(goal_id)
        pending = [m for m in milestones if m.status == MilestoneStatus.PENDING]

        if not pending:
            await self._store.update_status(goal_id, GoalStatus.COMPLETED)
            await self._push(Notification(
                content=f"Goal <b>{_html.escape(goal.title)}</b> is complete!\n\n<i>{_html.escape(goal.success_condition)}</i>",
                format="html",
                urgency="high",
            ))
            log.info("goal_completed", goal_id=str(goal_id))
            return

        next_milestone = pending[0]

        gate = await self._store.get_pending_gate(goal_id)
        if gate is not None and self._gate_should_fire(gate, next_milestone, milestones):
            completed = [m for m in milestones if m.status in _DONE_MILESTONE_STATUSES]
            await self._fire_gate(goal, gate, completed, pending)
            return

        await self._store.update_milestone(next_milestone.id, MilestoneStatus.IN_PROGRESS)
        log.info("milestone_started", goal_id=str(goal_id), sequence=next_milestone.sequence, title=next_milestone.title)

        try:
            output = await self._execute_milestone(next_milestone)
            await self._store.update_milestone(next_milestone.id, MilestoneStatus.COMPLETED, output=output)
            log.info("milestone_completed", goal_id=str(goal_id), sequence=next_milestone.sequence)
        except GoalExecutionError as exc:
            error_msg = str(exc)
            log.warning("milestone_failed", goal_id=str(goal_id), sequence=next_milestone.sequence, error=error_msg)
            await self._store.update_milestone(next_milestone.id, MilestoneStatus.SKIPPED, output=f"Failed: {error_msg}")
            await self._store.add_learning(GoalLearning(
                goal_id=goal_id,
                content=f"Milestone {next_milestone.sequence} ({next_milestone.title}) failed: {error_msg}",
                source="milestone_completion",
            ))
            await self._push(Notification(
                content=(
                    f"Milestone <b>{_html.escape(next_milestone.title)}</b> failed.\n"
                    f"<code>{_html.escape(error_msg[:200])}</code>\n\n"
                    "Continuing to next step."
                ),
                format="html",
                urgency="high",
            ))
            asyncio.create_task(self.advance(goal_id))
            return

        try:
            learning_text = await self._planner.extract_learning(next_milestone.title, output)
            await self._store.add_learning(GoalLearning(
                goal_id=goal_id,
                content=learning_text,
                source="milestone_completion",
            ))
            await self._store.append_learnings(goal_id, learning_text)
        except Exception as exc:
            log.warning("learning_extraction_failed", error=str(exc))

        total = len(milestones)
        completed_count = sum(1 for m in milestones if m.status == MilestoneStatus.COMPLETED) + 1
        await self._push(Notification(
            content=f"<b>{_html.escape(next_milestone.title)}</b> done ({completed_count}/{total}).",
            format="html",
        ))

        asyncio.create_task(self.advance(goal_id))

    async def approve_plan(self, goal_id: UUID) -> bool:
        """Activate a goal after the user approves its plan. Returns False if not in planning state."""
        goal = await self._store.get_goal(goal_id)
        if goal is None or goal.status != GoalStatus.PLANNING:
            return False
        await self._store.update_status(goal_id, GoalStatus.ACTIVE)
        log.info("goal_plan_approved", goal_id=str(goal_id))
        asyncio.create_task(self.advance(goal_id))
        return True

    async def reject_plan(self, goal_id: UUID) -> bool:
        """Abandon a goal when the user rejects its plan."""
        goal = await self._store.get_goal(goal_id)
        if goal is None or goal.status != GoalStatus.PLANNING:
            return False
        await self._store.update_status(goal_id, GoalStatus.ABANDONED)
        log.info("goal_plan_rejected", goal_id=str(goal_id))
        return True

    async def handle_gate_approved(self, gate_id: UUID) -> None:
        gate = await self._store.get_gate(gate_id)
        if gate is None or gate.status != GateStatus.AWAITING_APPROVAL:
            return
        await self._store.resolve_gate(gate_id, GateStatus.APPROVED)
        await self._store.update_status(gate.goal_id, GoalStatus.ACTIVE)
        log.info("gate_approved", gate_id=str(gate_id), goal_id=str(gate.goal_id))
        asyncio.create_task(self.advance(gate.goal_id))

    async def handle_gate_stopped(self, gate_id: UUID) -> None:
        gate = await self._store.get_gate(gate_id)
        if gate is None or gate.status != GateStatus.AWAITING_APPROVAL:
            return
        await self._store.resolve_gate(gate_id, GateStatus.STOPPED)
        await self._store.update_status(gate.goal_id, GoalStatus.ABANDONED)
        goal = await self._store.get_goal(gate.goal_id)
        title = goal.title if goal else str(gate.goal_id)
        await self._push(Notification(
            content=f"Goal <b>{_html.escape(title)}</b> stopped.",
            format="html",
            urgency="high",
        ))
        log.info("gate_stopped", gate_id=str(gate_id), goal_id=str(gate.goal_id))

    async def handle_gate_redirected(self, gate_id: UUID, feedback: str) -> None:
        gate = await self._store.get_gate(gate_id)
        if gate is None or gate.status != GateStatus.AWAITING_APPROVAL:
            return

        goal = await self._store.get_goal(gate.goal_id)
        if goal is None:
            return

        await self._store.add_learning(GoalLearning(
            goal_id=gate.goal_id,
            content=f"User redirect at checkpoint '{gate.title}': {feedback}",
            source="gate_feedback",
        ))
        await self._store.append_learnings(gate.goal_id, f"User redirect: {feedback}")

        milestones = await self._store.list_milestones(gate.goal_id)
        completed = [m for m in milestones if m.status == MilestoneStatus.COMPLETED]
        next_seq = max((m.sequence for m in completed), default=0) + 1

        try:
            new_milestones, new_gates = await self._planner.replan_remaining(
                goal, completed, feedback, next_seq
            )
        except Exception as exc:
            log.warning("replan_failed", error=str(exc))
            await self._push(Notification(
                content=f"Could not replan goal: {_html.escape(str(exc))}",
                format="html",
                urgency="high",
            ))
            return

        for m in new_milestones:
            m.goal_id = gate.goal_id
        for g in new_gates:
            g.goal_id = gate.goal_id

        await self._store.replace_pending_milestones(gate.goal_id, new_milestones)
        await self._store.replace_pending_gates(gate.goal_id, new_gates)

        await self._store.resolve_gate(gate_id, GateStatus.REDIRECTED, user_feedback=feedback)
        await self._store.update_status(gate.goal_id, GoalStatus.ACTIVE)
        log.info("gate_redirected", gate_id=str(gate_id), goal_id=str(gate.goal_id))
        asyncio.create_task(self.advance(gate.goal_id))

    # ── Private ────────────────────────────────────────────────────────────────

    @staticmethod
    def _gate_should_fire(
        gate,
        next_milestone: Milestone,
        milestones: list[Milestone],
    ) -> bool:
        if gate.status != GateStatus.PENDING:
            return False
        if gate.after_sequence != next_milestone.sequence - 1:
            return False
        prior = [m for m in milestones if m.sequence == gate.after_sequence]
        if not prior:
            return False
        return prior[0].status in _DONE_MILESTONE_STATUSES

    async def _execute_milestone(self, milestone: Milestone) -> str:
        agent_name = milestone.agent_hint or "companion"
        try:
            agent = self._get_agent(agent_name)
        except Exception:
            agent = self._get_agent("companion")

        # Import here to avoid circular dependency at module level
        from ze_core.capability.types import GateDecision
        from ze_core.orchestration.types import AgentContext

        ctx = AgentContext(
            session_id=f"goal:{milestone.goal_id}",
            prompt=milestone.description,
            intent=milestone.intent,
            gate_decision=GateDecision.EXECUTE,
        )

        try:
            result = await agent.run(ctx)
        except GoalExecutionError:
            raise
        except Exception as exc:
            raise GoalExecutionError(
                f"Milestone {milestone.sequence} ({milestone.title}) failed: {exc}"
            ) from exc
        return result.response

    async def _fire_gate(
        self,
        goal: Goal,
        gate,
        completed: list[Milestone],
        pending: list[Milestone],
    ) -> None:
        context_lines = [f"• {m.title}: {m.output[:150]}" for m in completed] or ["• No milestones completed yet."]
        plan_lines = [f"• {m.title}" for m in pending[:5]]

        context_summary = "\n".join(context_lines)
        plan_summary = "\n".join(plan_lines)

        await self._store.fire_gate(gate.id, context_summary, plan_summary)
        await self._store.update_status(goal.id, GoalStatus.AWAITING_GATE)

        gate_id_str = str(gate.id)
        content = (
            f"<b>{_html.escape(goal.title)}</b> — checkpoint\n\n"
            f"<b>What was done:</b>\n{_html.escape(context_summary)}\n\n"
            f"<b>What comes next:</b>\n{_html.escape(plan_summary)}\n\n"
            "Approve to continue, or send new instructions."
        )

        await self._push(Notification(
            content=content,
            format="html",
            urgency="high",
            actions=[
                Action(label="Proceed", payload=_PAYLOAD_APPROVE.format(gate_id=gate_id_str)),
                Action(label="Stop",    payload=_PAYLOAD_STOP.format(gate_id=gate_id_str)),
                Action(label="Redirect", payload=_PAYLOAD_REDIRECT.format(gate_id=gate_id_str)),
            ],
        ))
        log.info("gate_fired", gate_id=str(gate.id), goal_id=str(goal.id))
