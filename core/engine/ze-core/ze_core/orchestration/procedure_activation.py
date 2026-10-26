"""Orchestration helpers for procedure discovery, traces, and invocation close-out."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from langchain_core.runnables import RunnableConfig

from ze_agents.types import AgentContext, AgentResult, ProcedureInvocation
from ze_logging import get_logger
from ze_memory.procedures.discovery import format_procedure_guidance
from ze_memory.procedures.types import (
    CapabilityDecision,
    ProcedureActionOutcome,
    ProcedureOutcome,
    ProcedureTaskContext,
)

log = get_logger(__name__)


def facts_from_memory(memory: Any) -> list[str]:
    facts = getattr(memory, "facts", None) or []
    lines: list[str] = []
    for fact in facts:
        predicate = getattr(fact, "predicate", getattr(fact, "key", ""))
        value = getattr(fact, "value", "")
        lines.append(f"{predicate}: {value}")
    return lines


async def attach_procedure_matches(
    ctx: AgentContext,
    config: RunnableConfig,
    agent_name: str,
) -> None:
    discovery = config["configurable"].get("procedure_discovery")
    if discovery is None:
        return
    agent_tools: frozenset[str] = frozenset()
    try:
        from ze_agents.registry import get_agent

        agent = get_agent(agent_name)
        agent_tools = frozenset(getattr(agent, "tools", None) or [])
    except Exception:
        agent_tools = frozenset()
    try:
        matches = await discovery.match(
            ProcedureTaskContext(
                caller=agent_name,
                task_text=ctx.prompt,
                available_facts=facts_from_memory(ctx.memory),
                thread_id=ctx.session_id,
            ),
            agent_allowed_tools=agent_tools,
            capability_allowed_tools=agent_tools,
        )
    except Exception as exc:
        log.warning("procedure_discovery_failed", error=str(exc))
        return
    ctx.procedure_matches = matches
    ctx.procedure_guidance = format_procedure_guidance(matches)


async def record_guided_actions(
    invocation: ProcedureInvocation | None,
    result: AgentResult,
    config: RunnableConfig,
) -> None:
    activator = config["configurable"].get("procedure_activator")
    invocation_id = _invocation_uuid(invocation)
    if activator is None or invocation_id is None:
        return
    for index, call in enumerate(getattr(result, "tool_calls", None) or []):
        name = getattr(call, "tool_name", "") or ""
        if name == "invoke_procedure":
            continue
        success = bool(getattr(call, "success", False))
        gate = str(getattr(call, "gate", "none") or "none")
        if gate in ("denied", "refused", "refused_over_cap", "expired"):
            decision = CapabilityDecision.DENIED
            outcome = ProcedureActionOutcome.NOT_EXECUTED
        elif gate == "parked":
            decision = CapabilityDecision.AWAITING_CONFIRMATION
            outcome = ProcedureActionOutcome.NOT_EXECUTED
        elif gate == "duplicate":
            # Approved, but the one run is recorded on the call it repeats.
            decision = CapabilityDecision.ALLOWED
            outcome = ProcedureActionOutcome.NOT_EXECUTED
        elif success:
            decision = CapabilityDecision.ALLOWED
            outcome = ProcedureActionOutcome.SUCCEEDED
        else:
            decision = CapabilityDecision.ALLOWED
            outcome = ProcedureActionOutcome.FAILED
        try:
            await activator.record_action(
                invocation_id,
                step_ref=name or f"step-{index + 1}",
                action_trace_ref=name,
                capability_decision=decision,
                outcome=outcome,
            )
        except Exception as exc:
            log.warning("procedure_action_link_failed", error=str(exc))


def _invocation_uuid(invocation: ProcedureInvocation | None) -> UUID | None:
    if invocation is None or not invocation.invocation_id:
        return None
    try:
        return UUID(str(invocation.invocation_id))
    except ValueError:
        return None


def _results_by_subtask(state: dict) -> dict[int, AgentResult]:
    """Subtask index to its result. `subtask_results` is ordered by completed index,
    so a disabled or parked subtask has no entry and a position is not an index."""
    indexes = [int(i) for i in state.get("completed_subtask_indexes") or []]
    results = dict(zip(indexes, state.get("subtask_results") or []))
    single = state.get("agent_result")
    if single is not None:
        results[0] = single
    return results


async def complete_procedure_invocations(
    state: dict,
    config: RunnableConfig,
) -> None:
    """Close every invocation the turn started, each with its own subtask's result."""
    invocations: list[ProcedureInvocation] = list(
        state.get("procedure_invocations") or []
    )
    if not invocations:
        return
    if len(invocations) > 1:
        log.info("procedure_invocations_extra", count=len(invocations))
    activator = config["configurable"].get("procedure_activator")
    if activator is None:
        return
    results = _results_by_subtask(state)
    for invocation in invocations:
        invocation_id = _invocation_uuid(invocation)
        if invocation_id is None:
            continue
        result = results.get(invocation.subtask)
        calls = list(getattr(result, "tool_calls", None) or []) if result else []
        guided = [c for c in calls if getattr(c, "tool_name", "") != "invoke_procedure"]
        if any(not getattr(c, "success", False) for c in guided):
            outcome = ProcedureOutcome.FAILED
            summary = "procedure-guided turn included a failed action"
        elif guided and all(getattr(c, "success", False) for c in guided):
            outcome = ProcedureOutcome.SUCCEEDED
            summary = "procedure-guided turn completed"
        else:
            outcome = ProcedureOutcome.ABANDONED
            summary = "procedure invoked without completed guided actions"
        try:
            await activator.complete(invocation_id, outcome=outcome, summary=summary)
        except Exception as exc:
            log.warning("procedure_invocation_complete_failed", error=str(exc))


def procedure_usage_trace(state: dict) -> dict[str, str] | None:
    """The trace shows the lowest subtask's invocation (research R7)."""
    invocations = state.get("procedure_invocations") or []
    if not invocations:
        return None
    invocation = min(invocations, key=lambda inv: inv.subtask)
    invocation_id, procedure_id, version_id = (
        invocation.invocation_id,
        invocation.procedure_id,
        invocation.version_id,
    )
    if not invocation_id or not procedure_id or not version_id:
        return None
    return {
        "invocation_id": str(invocation_id),
        "procedure_id": str(procedure_id),
        "version_id": str(version_id),
    }
