"""Built-in delegate_to_agent harness tool.

Not registered via @tool — handled specially in agentic_loop alongside
_OPENROUTER_TOOL_SCHEMAS, which keeps it out of the tool registry and avoids
conflicts with clear_tool_registry() in tests.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from ze_agents.budget import BUDGET_EXHAUSTED_ERROR, remaining_seconds
from ze_agents.errors import AgentAbortedError, LoopParked
from ze_agents.park import ParkedLoop
from ze_agents.registry import get_agent
from ze_logging import get_logger
from ze_agents.nested_tools import nested_row
from ze_agents.types import AgentContext, ToolCall, WriteGateState, add_sources

log = get_logger(__name__)

DELEGATE_TOOL_NAME = "delegate_to_agent"
_DELEGATE_MAX_DEPTH = 1
_CONDUCTOR_NAME = "companion"
DELEGATE_PER_SPECIALIST_CAP = 2
DELEGATE_TURN_CAP = 6
_ASK_USER_ERROR = (
    "ask_user: tell the user this specialist stalled or the turn delegate cap "
    "was reached; do not retry silently"
)
_IN_FLIGHT_LEDGER = frozenset({"planned", "running", "awaiting_confirmation"})

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
    ledger = ctx.conductor.ledger
    if status in {"stalled", "replanned", "ask_user"}:
        if status == "stalled":
            for item in ledger:
                if item.get("agent") != agent_name:
                    continue
                if item.get("status") in {"planned", "running"}:
                    item["status"] = status
                    if request_id:
                        item["request_id"] = request_id
                    return
        entry = {"agent": agent_name, "status": status}
        if request_id:
            entry["request_id"] = request_id
        ledger.append(entry)
        return
    entry: dict[str, str] | None = None
    for item in ledger:
        if item.get("agent") != agent_name:
            continue
        if item.get("status") in _IN_FLIGHT_LEDGER:
            entry = item
            break
    if entry is None:
        entry = {"agent": agent_name, "status": status}
        ledger.append(entry)
    entry["status"] = status
    if request_id:
        entry["request_id"] = request_id


def _would_exceed_delegate_caps(ctx: AgentContext, agent_name: str) -> bool:
    tally = ctx.conductor.tally
    return (
        tally.counts.get(agent_name, 0) >= DELEGATE_PER_SPECIALIST_CAP
        or tally.total >= DELEGATE_TURN_CAP
    )


def _bump_delegate_counts(ctx: AgentContext, agent_name: str) -> None:
    tally = ctx.conductor.tally
    tally.counts[agent_name] = tally.counts.get(agent_name, 0) + 1
    tally.total += 1


def _has_stalled(ctx: AgentContext, agent_name: str) -> bool:
    return any(
        item.get("agent") == agent_name and item.get("status") == "stalled"
        for item in ctx.conductor.ledger
    )


def _inject_stall_context(arguments: dict[str, Any], detail: str) -> dict[str, Any]:
    args = dict(arguments)
    prior = args.get("prior_outputs")
    extra = args.get("inputs")
    has_prior = isinstance(prior, str) and prior.strip()
    has_inputs = isinstance(extra, str) and extra.strip()
    if not has_prior and not has_inputs:
        args["prior_outputs"] = (
            f"Previous attempt stalled: {detail}. "
            "Try a different approach or smaller scope."
        )
    return args


def _is_empty_response(response: str | None) -> bool:
    return not (response or "").strip()


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
    resume: ParkedLoop | None = None,
) -> ToolCall:
    """Execute a delegate_to_agent tool call from inside agentic_loop.

    With `resume`, re-enter the specialist's parked loop instead of starting it.
    """
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

    agent_name = agent_name.strip()

    if resume is None and _would_exceed_delegate_caps(ctx, agent_name):
        log.warning("delegate_cap_exceeded", to_agent=agent_name)
        _update_conductor_ledger(ctx, agent_name, "ask_user")
        return _failed(arguments, _ASK_USER_ERROR)

    if resume is None and _has_stalled(ctx, agent_name):
        detail = str(ctx.conductor.stalls.get(agent_name) or "empty or error")
        arguments = _inject_stall_context(arguments, detail)
        _update_conductor_ledger(ctx, agent_name, "replanned")

    try:
        instance = get_agent(agent_name)
    except Exception as exc:
        _bump_delegate_counts(ctx, agent_name)
        ctx.conductor.stalls[agent_name] = str(exc)
        _update_conductor_ledger(ctx, agent_name, "stalled")
        return _failed(arguments, str(exc))

    if resume is None:
        _bump_delegate_counts(ctx, agent_name)

    prompt = assemble_delegate_prompt(arguments)
    sub_ctx = AgentContext(
        session_id=ctx.session_id,
        prompt=prompt,
        memory=ctx.memory,
        contacts=ctx.contacts,
        persona=ctx.persona,
        timezone=ctx.timezone,
        model=None,
        messages=[{"role": "user", "content": prompt}],
        reporter=ctx.reporter,
        identity_builder=ctx.identity_builder,
        abort_token=ctx.abort_token,
        write_gate=WriteGateState(
            resume=resume,
            decisions=ctx.write_gate.decisions,
            pre_approved=ctx.write_gate.pre_approved,
            round=ctx.write_gate.round,
            approval_request_id=ctx.write_gate.approval_request_id,
            retry_mode=ctx.write_gate.retry_mode,
        ),
        tool_sink=ctx.tool_sink,
        script_runner=ctx.script_runner,
        extensions={"_delegate_depth": depth + 1},
    )

    _update_conductor_ledger(ctx, agent_name, "running")
    await _emit_conductor_progress(ctx, agent_name)
    log.info("delegate_start", from_agent=caller_name, to_agent=agent_name, depth=depth)
    left = remaining_seconds(ctx)
    if left is not None and left <= 0:
        ctx.conductor.stalls[agent_name] = "time budget used up"
        _update_conductor_ledger(ctx, agent_name, "stalled")
        return _failed(arguments, BUDGET_EXHAUSTED_ERROR)
    try:
        if left is None:
            result = await instance.run(sub_ctx)
        else:
            result = await asyncio.wait_for(instance.run(sub_ctx), timeout=left)
    except AgentAbortedError:
        raise
    except asyncio.TimeoutError as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        remaining = remaining_seconds(ctx)
        if remaining is None or remaining > 0:
            # The specialist raised its own timeout (a socket, an HTTP call).
            log.warning("delegate_error", to_agent=agent_name, error=str(exc))
            ctx.conductor.stalls[agent_name] = str(exc) or "timed out"
            _update_conductor_ledger(ctx, agent_name, "stalled")
            return _failed(arguments, str(exc) or "timed out", duration_ms=duration_ms)
        log.warning("delegate_over_budget", to_agent=agent_name)
        ctx.conductor.stalls[agent_name] = "time budget used up"
        _update_conductor_ledger(ctx, agent_name, "stalled")
        return ToolCall(
            tool_name=DELEGATE_TOOL_NAME,
            args=arguments,
            result={"tool_calls": [nested_row(c) for c in sub_ctx.tool_calls]},
            duration_ms=duration_ms,
            success=False,
            error=(
                f"{agent_name} did not finish in time and may have partly run: "
                f"check before repeating anything it could have changed. "
                f"{BUDGET_EXHAUSTED_ERROR}"
            ),
        )
    except LoopParked as parked:
        log.info("delegate_parked", to_agent=agent_name)
        _update_conductor_ledger(ctx, agent_name, "awaiting_confirmation")
        return ToolCall(
            tool_name=DELEGATE_TOOL_NAME,
            args=arguments,
            result=None,
            duration_ms=int((time.monotonic() - start) * 1000),
            success=False,
            error="parked: awaiting the user's approval",
            gate="parked",
            child_loop=parked.loop,
        )
    except Exception as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        log.warning("delegate_error", to_agent=agent_name, error=str(exc))
        ctx.conductor.stalls[agent_name] = str(exc)
        _update_conductor_ledger(ctx, agent_name, "stalled")
        return _failed(arguments, str(exc), duration_ms=duration_ms)

    add_sources(ctx.sources, sub_ctx.sources)
    duration_ms = int((time.monotonic() - start) * 1000)
    nested = [nested_row(call) for call in result.tool_calls]
    if _is_empty_response(result.response):
        log.warning("delegate_stalled_empty", to_agent=agent_name)
        ctx.conductor.stalls[agent_name] = "empty response"
        _update_conductor_ledger(ctx, agent_name, "stalled")
        return ToolCall(
            tool_name=DELEGATE_TOOL_NAME,
            args=arguments,
            result={"response": result.response, "tool_calls": nested},
            duration_ms=duration_ms,
            success=False,
            error="stalled: empty response",
            gate="none",
        )

    log.info("delegate_done", to_agent=agent_name, duration_ms=duration_ms)
    _update_conductor_ledger(ctx, agent_name, "done")
    return ToolCall(
        tool_name=DELEGATE_TOOL_NAME,
        args=arguments,
        result={"response": result.response, "tool_calls": nested},
        duration_ms=duration_ms,
        success=True,
        gate="none",
    )
