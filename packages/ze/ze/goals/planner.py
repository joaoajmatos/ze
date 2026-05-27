"""Ze wiring for ze-core GoalPlanner (workflow_plan_model from settings)."""

from __future__ import annotations

from ze_core.goals.types import Goal, Milestone, VerificationGate
from ze.openrouter.client import OpenRouterClient
from ze.settings import Settings
from ze_core.goals.planner import GoalPlanner as _GoalPlanner


class GoalPlanner:
    def __init__(self, openrouter_client: OpenRouterClient, settings: Settings) -> None:
        self._planner = _GoalPlanner(
            client=openrouter_client,
            model=settings.workflow_plan_model,
        )

    async def plan(self, goal: Goal) -> tuple[list[Milestone], list[VerificationGate]]:
        return await self._planner.plan(goal)

    async def replan_remaining(
        self,
        goal: Goal,
        completed_milestones: list[Milestone],
        feedback: str,
        next_sequence: int,
    ) -> tuple[list[Milestone], list[VerificationGate]]:
        return await self._planner.replan_remaining(
            goal, completed_milestones, feedback, next_sequence
        )

    async def extract_learning(self, milestone_title: str, output: str) -> str:
        return await self._planner.extract_learning(milestone_title, output)
