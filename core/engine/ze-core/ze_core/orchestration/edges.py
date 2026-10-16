from __future__ import annotations

from ze_core.orchestration.state import AgentState


def after_embed_route(state: AgentState) -> str:
    envelope = state["envelope"]
    if envelope and envelope.is_compound:
        return "decompose"
    return "fetch_context"


def after_decompose(state: AgentState) -> str:
    """Haiku sequential multi-specialist turns are rewritten to companion in decompose."""
    return "fetch_context"


def after_preflight(state: AgentState) -> str:
    if state.get("blocked"):
        return "end_blocked"
    if state.get("budget_status") and not state.get("budget_approved"):
        return "await_budget_confirmation"
    return "execute_tool"


def after_await_budget_confirmation(state: AgentState) -> str:
    return "record_trace" if state.get("final_response") else "execute_tool"


def after_execute_tool(state: AgentState) -> str:
    if state.get("write_confirmation") is not None and state.get("parked_subtasks"):
        return "await_write_confirmation"
    return "correlate"


def after_correlate(state: AgentState) -> str:
    envelope = state.get("envelope")
    if envelope and envelope.is_compound and state.get("subtask_results"):
        return "synthesize"
    return "record_trace"


def after_surface_loops(state: AgentState) -> str:
    """Same routing decision as `after_correlate`, run one node later now that
    `surface_loops` sits between `correlate` and the synthesize/record_trace fork."""
    envelope = state.get("envelope")
    if envelope and envelope.is_compound and state.get("subtask_results"):
        return "synthesize"
    return "record_trace"
