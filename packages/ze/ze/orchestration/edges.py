"""Ze graph edges — ze-core defaults plus workflow and plan_sequential routing."""

from ze_core.capability.types import GateDecision
from ze.orchestration.state import AgentState
from ze_core.orchestration.edges import (
    after_capability_check,
    after_embed_route,
    after_execute_tool,
)

__all__ = [
    "after_capability_check",
    "after_embed_route",
    "after_execute_tool",
    "after_decompose",
    "after_capability_check_workflow",
    "after_verify_step",
]


def after_decompose(state: AgentState) -> str:
    """Sequential compound tasks need WorkflowPlanner before fetch_context."""
    envelope = state.get("envelope")
    if envelope and envelope.is_sequential:
        return "plan_sequential"
    return "fetch_context"


# ── Workflow graph edges ───────────────────────────────────────────────────────

def after_capability_check_workflow(state: AgentState) -> str:
    """In workflow mode all steps execute directly — workflow creation was the gate."""
    decision = state.get("gate_decision")
    if decision == GateDecision.BLOCKED:
        return "workflow_failed"
    return "execute_tool"


def after_verify_step(state: AgentState) -> str:
    step_results = state.get("workflow_step_results") or []
    if step_results and not step_results[-1].success:
        return "workflow_failed"
    steps = state.get("workflow_steps") or []
    if state.get("current_step_index", 0) >= len(steps):
        return "workflow_synthesize"
    return "load_workflow_step"
