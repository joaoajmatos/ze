"""Built-in delegate_to_agent harness tool.

Not registered via @tool — handled specially in agentic_loop alongside
_OPENROUTER_TOOL_SCHEMAS, which keeps it out of the tool registry and avoids
conflicts with clear_tool_registry() in tests.
"""

from __future__ import annotations

import inspect
import time
from typing import Any
from uuid import uuid4

from ze_agents.errors import AgentAbortedError
from ze_agents.interrupt import tool_interrupt_fn
from ze_agents.registry import get_agent
from ze_logging import get_logger
from ze_agents.types import AgentContext, GateDecision, ToolCall

log = get_logger(__name__)

DELEGATE_TOOL_NAME = "delegate_to_agent"
_DELEGATE_MAX_DEPTH = 1
_CONDUCTOR_NAME = "companion"

DELEGATE_TOOL_SCHEMA: dict = {
    "type": "function",
    "function": {
        "name": DELEGATE_TOOL_NAME,
        "description": (
            "Delegate a subtask to a specialised agent and return its complete response. "
            "Only the companion conductor may call this. Pass a fat brief: what to achieve, "
            "any prior outputs or extra inputs, the desired answer shape, and when to stop."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "description": "Name of the specialised agent to run (not companion).",
                },
                "objective": {
                    "type": "string",
                    "description": "What the specialist must achieve.",
                },
                "prior_outputs": {
                    "type": "string",
                    "description": "Prior specialist text or identifiers for this step.",
                },
                "inputs": {
                    "type": "string",
                    "description": "Extra facts: constraints, ids, recipient, times.",
                },
                "output_shape": {
                    "type": "string",
                    "description": "Hint for the shape of the worker's answer.",
                },
                "stop_condition": {
                    "type": "string",
                    "description": "Hint for when the worker should stop.",
                },
                "intent": {
                    "type": "string",
                    "description": (
                        "Optional specialist intent key (e.g. read, create). "
                        "Omitted uses the specialist's default mode."
                    ),
                },
            },
            "required": ["agent_name", "objective"],
        },
    },
}


def _failed(arguments: dict[str, Any], error: str, duration_ms: int = 0) -> ToolCall:
    return ToolCall(
        tool_name=DELEGATE_TOOL_NAME,
        args=arguments,
        result=None,
        duration_ms=duration_ms,
        success=False,
        error=error,
    )


def assemble_delegate_prompt(arguments: dict[str, Any]) -> str:
    """Build isolated worker user content from a fat brief."""
    lines = [f"Objective: {arguments['objective'].strip()}"]
    optional = (
        ("prior_outputs", "Prior outputs"),
        ("inputs", "Inputs"),
        ("output_shape", "Output shape"),
        ("stop_condition", "Stop"),
    )
    for key, label in optional:
        value = arguments.get(key)
        if isinstance(value, str) and value.strip():
            lines.append(f"{label}: {value.strip()}")
    return "\n".join(lines)


def _update_conductor_ledger(
    ctx: AgentContext,
    agent_name: str,
    status: str,
    request_id: str | None = None,
) -> None:
    ledger = getattr(ctx, "conductor_ledger", None)
    if ledger is None:
        ctx.conductor_ledger = ledger = []
    entry: dict[str, str] | None = None
    for item in ledger:
        if item.get("agent") != agent_name:
            continue
        if item.get("status") in ("planned", "running", "awaiting_confirmation"):
            entry = item
            break
    if entry is None:
        entry = {"agent": agent_name, "status": status}
        ledger.append(entry)
    entry["status"] = status
    if request_id:
        entry["request_id"] = request_id


async def _emit_conductor_progress(ctx: AgentContext, agent_name: str) -> None:
    reporter = ctx.reporter
    if reporter is None:
        return
    key = None
    if agent_name == "calendar":
        key = "conductor.checking_calendar"
    elif agent_name == "messenger":
        key = "conductor.drafting_mail"
    if key is None:
        return
    await reporter.emit(key)


async def run_delegate(
    arguments: dict[str, Any],
    ctx: AgentContext,
    iteration: int,
    *,
    caller_name: str,
) -> ToolCall:
    """Execute a delegate_to_agent tool call from inside agentic_loop."""
    agent_name: str = arguments.get("agent_name", "") or ""
    objective: str = arguments.get("objective", "") or ""
    depth: int = ctx.extensions.get("_delegate_depth", 0)  # type: ignore[assignment]

    start = time.monotonic()

    if caller_name != _CONDUCTOR_NAME:
        log.warning("delegate_refused_caller", caller=caller_name, to_agent=agent_name)
        return _failed(arguments, "delegate_to_agent is only available to companion")

    if not agent_name.strip() or agent_name.strip() == _CONDUCTOR_NAME:
        log.warning("delegate_refused_target", target=agent_name)
        return _failed(arguments, "cannot delegate to companion")

    if not objective.strip():
        return _failed(arguments, "objective is required")

    if depth >= _DELEGATE_MAX_DEPTH:
        msg = f"delegation depth limit exceeded (max {_DELEGATE_MAX_DEPTH})"
        log.warning("delegate_depth_exceeded", agent=agent_name, depth=depth)
        return _failed(arguments, msg)

    try:
        instance = get_agent(agent_name)
    except Exception as exc:
        return _failed(arguments, str(exc))

    declared_intent = arguments.get("intent")
    intent = declared_intent.strip() if isinstance(declared_intent, str) else ""
    evaluator = ctx.evaluate_delegate
    if evaluator is None:
        return _failed(arguments, "delegate gate evaluator missing")
    decision = evaluator(agent_name, intent)
    if inspect.isawaitable(decision):
        decision = await decision

    if decision == GateDecision.BLOCKED:
        log.warning("delegate_blocked", to_agent=agent_name, intent=intent)
        _update_conductor_ledger(ctx, agent_name, "skipped")
        return _failed(arguments, "blocked by capability gate")

    if decision == GateDecision.AWAIT_CONFIRMATION:
        interrupt_fn = tool_interrupt_fn.get()
        request_id = str(uuid4())
        if interrupt_fn is None:
            return _failed(arguments, "confirmation required but no interrupt")
        _update_conductor_ledger(
            ctx, agent_name, "awaiting_confirmation", request_id=request_id
        )
        resume = interrupt_fn(
            {
                "kind": "delegate",
                "request_id": request_id,
                "prompt": f"Allow {agent_name} to: {objective.strip()}",
                "agent": agent_name,
                "intent": intent,
                "editable": False,
                "proposed": "",
            }
        )
        choice = "approve"
        if isinstance(resume, dict):
            choice = str(resume.get("choice") or "approve")
        elif isinstance(resume, str):
            choice = resume
        if choice != "approve":
            _update_conductor_ledger(ctx, agent_name, "denied", request_id=request_id)
            return _failed(arguments, "denied by user")
        decision = GateDecision.EXECUTE

    prompt = assemble_delegate_prompt(arguments)
    sub_ctx = AgentContext(
        session_id=ctx.session_id,
        prompt=prompt,
        intent=agent_name,
        gate_decision=decision,
        memory=ctx.memory,
        contacts=ctx.contacts,
        persona=ctx.persona,
        model=None,
        messages=[{"role": "user", "content": prompt}],
        reporter=ctx.reporter,
        identity_builder=ctx.identity_builder,
        abort_token=ctx.abort_token,
        extensions={"_delegate_depth": depth + 1},
    )

    _update_conductor_ledger(ctx, agent_name, "running")
    await _emit_conductor_progress(ctx, agent_name)
    log.info("delegate_start", from_agent=caller_name, to_agent=agent_name, depth=depth)
    try:
        result = await instance.run(sub_ctx)
    except AgentAbortedError:
        raise
    except Exception as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        log.warning("delegate_error", to_agent=agent_name, error=str(exc))
        _update_conductor_ledger(ctx, agent_name, "skipped")
        return _failed(arguments, str(exc), duration_ms=duration_ms)

    duration_ms = int((time.monotonic() - start) * 1000)
    log.info("delegate_done", to_agent=agent_name, duration_ms=duration_ms)
    _update_conductor_ledger(ctx, agent_name, "done")
    nested = [
        {
            "tool_name": call.tool_name,
            "args": call.args,
            "result": call.result,
            "duration_ms": call.duration_ms,
            "success": call.success,
            "error": call.error,
        }
        for call in result.tool_calls
    ]
    return ToolCall(
        tool_name=DELEGATE_TOOL_NAME,
        args=arguments,
        result={"response": result.response, "tool_calls": nested},
        duration_ms=duration_ms,
        success=True,
    )
