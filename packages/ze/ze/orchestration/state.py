"""Ze AgentState — ze-core conversation state plus workflow execution fields."""

from __future__ import annotations

from typing import TypedDict
from uuid import UUID

from ze_core.orchestration.state import AgentState as CoreAgentState


class AgentState(CoreAgentState, total=False):
    """Extended state for Ze workflow graph and dynamic sequential plans."""

    # ── Workflow execution (workflow_graph only) ──────────────────────────────
    workflow_id: UUID | None
    workflow_execution_id: UUID | None
    workflow_steps: list | None  # list[WorkflowStep]
    current_step_index: int
    workflow_step_results: list  # list[StepResult]

    # ── Dynamic plan (plan_sequential node) ───────────────────────────────────
    dynamic_plan_steps: list | None  # list[WorkflowStep]
    dynamic_plan_high_risk: list  # indices requiring approval
