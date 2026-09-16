"""Orchestration helpers for procedure discovery, traces, and invocation close-out."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from langchain_core.runnables import RunnableConfig

from ze_agents.types import AgentContext, AgentResult, GateDecision
from ze_logging import get_logger
from ze_memory.procedures.discovery import format_procedure_guidance, intersect_tools
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


def capability_allowed_tools(
    gate_decision: GateDecision | None, candidate_tools: frozenset[str]
) -> frozenset[str]:
    if gate_decision is GateDecision.BLOCKED:
        return frozenset()
    if gate_decision is GateDecision.DRAFT:
        from ze_agents.tool import get_tool

        readable: set[str] = set()
        for name in candidate_tools:
            try:
                spec = get_tool(name)
            except Exception:
                continue
            if spec.access.value == "read":
                readable.add(name)
        return frozenset(readable)
    return candidate_tools


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
    ctx: AgentContext,
    result: AgentResult,
    config: RunnableConfig,
) -> None:
    activator = config["configurable"].get("procedure_activator")
    invocation_raw = getattr(ctx, "procedure_invocation_id", None)
    if activator is None or not invocation_raw:
        return
    try:
        invocation_id = UUID(str(invocation_raw))
    except ValueError:
        return
    gate = getattr(ctx, "gate_decision", None)
    for index, call in enumerate(getattr(result, "tool_calls", None) or []):
        name = getattr(call, "tool_name", "") or ""
        if name == "invoke_procedure":
            continue
        success = bool(getattr(call, "success", False))
        is_draft = bool(getattr(call, "is_draft", False))
        error = str(getattr(call, "error", "") or "")
        if gate is GateDecision.BLOCKED or "blocked by the capability gate" in error:
            decision = CapabilityDecision.DENIED
            outcome = ProcedureActionOutcome.NOT_EXECUTED
        elif gate is GateDecision.AWAIT_CONFIRMATION or is_draft:
            decision = CapabilityDecision.AWAITING_CONFIRMATION
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


async def complete_procedure_invocation(
    ctx: AgentContext | None,
    result: AgentResult | None,
    config: RunnableConfig,
) -> None:
    if ctx is None:
        return
    activator = config["configurable"].get("procedure_activator")
    invocation_raw = getattr(ctx, "procedure_invocation_id", None)
    if activator is None or not invocation_raw:
        return
    try:
        invocation_id = UUID(str(invocation_raw))
    except ValueError:
        return
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
        await activator.complete(
            invocation_id, outcome=outcome, summary=summary
        )
    except Exception as exc:
        log.warning("procedure_invocation_complete_failed", error=str(exc))


def procedure_usage_trace(ctx: AgentContext | None) -> dict[str, str] | None:
    if ctx is None:
        return None
    invocation_id = getattr(ctx, "procedure_invocation_id", None)
    procedure_id = getattr(ctx, "procedure_invoked_id", None)
    version_id = getattr(ctx, "procedure_invoked_version_id", None)
    if not invocation_id or not procedure_id or not version_id:
        return None
    return {
        "invocation_id": str(invocation_id),
        "procedure_id": str(procedure_id),
        "version_id": str(version_id),
    }


def intersect_for_invocation(
    agent_allowed: frozenset[str],
    capability_allowed: frozenset[str],
    procedure_relevant: frozenset[str],
) -> frozenset[str]:
    return intersect_tools(agent_allowed, capability_allowed, procedure_relevant)
