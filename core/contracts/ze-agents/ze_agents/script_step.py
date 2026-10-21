"""The `run_tool_script` step: builds the stub, serves a script's reads, shapes the result."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime, time as dtime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from ze_agents.errors import AgentAbortedError
from ze_agents.scripts import (
    SCRIPT_TOOL_NAME,
    DispatchReply,
    ScriptContext,
    ScriptBudget,
    ScriptLimits,
    ScriptOutcome,
    ScriptRequest,
    current_script_budget,
    in_script_call,
)
from ze_agents.tool import ToolAccess
from ze_agents.types import AgentContext, ToolCall
from ze_logging import get_logger

if TYPE_CHECKING:
    from ze_agents.base_agent import BaseAgent

log = get_logger(__name__)

_PROCEDURE_INVOKE_TOOL = "invoke_procedure"
_DELEGATE_TOOL = "delegate_to_agent"
_STDERR_LINES = 20
_SHAPE_KEYS = 20
_TRUNCATED = "… [truncated]"
_REJECTED = "not_a_proposable_write"

_STATUS_KIND = {
    "exception": "exception",
    "bad_request": "bad_request",
    "busy": "sandbox_busy",
    "unavailable": "sandbox_unavailable",
    "resource_limit": "resource_limit",
    "killed": "exception",
}


@dataclass
class ScriptProposal:
    """One write the script proposed: runnable, or already rejected as a failed call."""

    tool: str
    args: dict[str, Any]
    rejected: ToolCall | None = None


@dataclass
class ScriptStepResult:
    tool_call: ToolCall
    proposals: list[ScriptProposal] = field(default_factory=list)


@dataclass
class _Run:
    step_id: str
    requests: int = 0
    limit: str | None = None
    inner: list[ToolCall] = field(default_factory=list)
    last_value: Any = None
    has_value: bool = False


_MAX_ID = 64
_SAFE_ID = re.compile(r"[^A-Za-z0-9_-]")
_PROPOSAL_SUFFIX = re.compile(r"^(.*)_w\d+$")


def proposal_call_id(model_call_id: str, index: int) -> str:
    """`<model id>_w<index>`, limited to `[A-Za-z0-9_-]` and 64 characters."""
    suffix = f"_w{index}"
    base = _SAFE_ID.sub("_", model_call_id)[: _MAX_ID - len(suffix)]
    return f"{base}{suffix}"


def script_parent_id(accumulated: list[ToolCall], call_id: str) -> str | None:
    """The script step a synthetic proposal id belongs to, found among earlier calls."""
    found = _PROPOSAL_SUFFIX.match(call_id)
    if found is None:
        return None
    prefix = found.group(1)
    cut = len(call_id) == _MAX_ID
    for call in accumulated:
        model_id = (call.script or {}).get("model_call_id")
        if not isinstance(model_id, str):
            continue
        if model_id == prefix or (cut and model_id.startswith(prefix)):
            return call.call_id
    return None


def _is_server_tool(name: str) -> bool:
    return name == "openrouter" or name.startswith(("openrouter:", "openrouter_"))


def _is_harness(name: str) -> bool:
    return name in (
        SCRIPT_TOOL_NAME,
        _DELEGATE_TOOL,
        _PROCEDURE_INVOKE_TOOL,
    ) or name.startswith("workspace_")


def data_read_names(agent: BaseAgent, ctx: AgentContext, names: list[str]) -> list[str]:
    """The visible tools a script may read through: no writes, UI, egress or harness tools."""
    from ze_agents.tool import registered_tools

    registered = registered_tools()
    out: list[str] = []
    for name in agent._visible_tool_names(ctx, names):
        spec = registered.get(name)
        if spec is None or _is_server_tool(name) or _is_harness(name):
            continue
        if spec.access is ToolAccess.WRITE or spec.produces_ui or spec.egress:
            continue
        out.append(name)
    return out


def _writable_names(agent: BaseAgent, ctx: AgentContext, names: list[str]) -> set[str]:
    from ze_agents.tool import registered_tools

    registered = registered_tools()
    return {
        n
        for n in agent._visible_tool_names(ctx, names)
        if n in registered and registered[n].access is ToolAccess.WRITE
    }


def _encode(value: Any) -> str:
    if isinstance(value, (datetime, date, dtime)):
        return value.isoformat()
    return str(value)


def _dumps(value: Any) -> str:
    try:
        return json.dumps(value, default=_encode)
    except (TypeError, ValueError):
        return json.dumps(str(value))


def _reply_value(result: Any, max_bytes: int) -> tuple[Any, str | None]:
    """The value a script receives: parsed JSON, ISO dates, string ids; dicts stay dicts."""
    if result is None:
        return None, None
    if isinstance(result, str):
        if len(result.encode()) > max_bytes:
            return None, "result_too_large"
        try:
            parsed = json.loads(result)
        except ValueError:
            return result, None
        if isinstance(parsed, (dict, list)):
            return parsed, None
        return result, None
    text = _dumps(result)
    if len(text.encode()) > max_bytes:
        return None, "result_too_large"
    return json.loads(text), None


def _cut_stored(result: Any, limit: int) -> Any:
    if result is None:
        return None
    text = result if isinstance(result, str) else _dumps(result)
    return text[:limit] if len(text) > limit else result


def _shape(value: Any) -> str:
    if isinstance(value, dict):
        return "dict keys: " + ", ".join(list(map(str, value))[:_SHAPE_KEYS])
    if isinstance(value, list):
        if value and isinstance(value[0], dict):
            keys = ", ".join(list(map(str, value[0]))[:_SHAPE_KEYS])
            return f"list[dict] keys: {keys}"
        return f"list[{type(value[0]).__name__ if value else 'empty'}] len {len(value)}"
    return type(value).__name__


def _error_body(
    kind: str, message: str, run: _Run | None = None, **extra: Any
) -> dict[str, Any]:
    body: dict[str, Any] = {"kind": kind, "message": message}
    if run is not None:
        body["completed"] = [
            {"name": c.tool_name, "success": c.success} for c in run.inner
        ]
    body.update(extra)
    return {"error": body}


def _refused(
    agent: BaseAgent, step_id: str, tool: Any, args: Any, error: str
) -> ToolCall:
    return ToolCall(
        agent=agent.name,
        tool_name=tool if isinstance(tool, str) else "invalid",
        args=args if isinstance(args, dict) else {},
        result=None,
        duration_ms=0,
        success=False,
        error=error,
        parent_call_id=step_id,
    )


def _failed_step(
    step_id: str,
    started: float,
    args: dict[str, Any],
    script: dict[str, Any],
    kind: str,
    message: str,
) -> ScriptStepResult:
    script["outcome"] = kind
    return ScriptStepResult(
        ToolCall(
            tool_name=SCRIPT_TOOL_NAME,
            args=args,
            result=_dumps(_error_body(kind, message)),
            duration_ms=int((time.monotonic() - started) * 1000),
            success=False,
            error=kind,
            call_id=step_id,
            started_at=started,
            script=script,
        )
    )


def _resolve_source(
    args: dict[str, Any], ctx: AgentContext
) -> tuple[str | None, str | None, str | None, str]:
    """Return (source, procedure_id, error_kind, message)."""
    procedure_id = args.get("procedure_id")
    source = args.get("source")
    if procedure_id is not None:
        for match in ctx.procedure_matches or []:
            if str(getattr(match, "procedure_id", "")) != str(procedure_id):
                continue
            state = getattr(match.state, "value", match.state)
            if (
                getattr(match, "source_kind", None) == "tool_script"
                and state == "ready"
            ):
                steps = list(getattr(match, "steps", []) or [])
                if steps and isinstance(steps[0], str):
                    return steps[0], str(procedure_id), None, ""
            break
        return (
            None,
            str(procedure_id),
            "procedure_not_script",
            ("that procedure is not a ready script procedure"),
        )
    if not isinstance(source, str) or not source.strip():
        return None, None, "bad_request", "give either source or procedure_id"
    return source, None, None, ""


def _validate_writes(
    agent: BaseAgent,
    ctx: AgentContext,
    names: list[str],
    raw: list[Any],
    limits: ScriptLimits,
    step_id: str,
) -> list[ScriptProposal]:
    writable = _writable_names(agent, ctx, names)
    proposals: list[ScriptProposal] = []
    for index, item in enumerate(raw[: limits.max_proposed_writes * 2]):
        tool = item.get("tool") if isinstance(item, dict) else None
        args = item.get("args") if isinstance(item, dict) else None
        valid = (
            isinstance(tool, str)
            and isinstance(args, dict)
            and tool in writable
            and index < limits.max_proposed_writes
        )
        if valid:
            proposals.append(ScriptProposal(tool=tool, args=args))
        else:
            proposals.append(
                ScriptProposal(
                    tool=tool if isinstance(tool, str) else "invalid",
                    args=args if isinstance(args, dict) else {},
                    rejected=_refused(agent, step_id, tool, args, _REJECTED),
                )
            )
    return proposals


def _model_text(
    outcome: ScriptOutcome, run: _Run, limits: ScriptLimits, script: dict[str, Any]
) -> tuple[str, bool, str | None]:
    """Return (text for the model, success, error kind)."""
    status = outcome.status
    if status == "timeout" and run.limit is None:
        run.limit = "wall_time"
    if run.limit in ("inner_calls", "spend", "wall_time"):
        script["limit"] = run.limit
        cap = {
            "inner_calls": limits.max_inner_calls,
            "spend": limits.max_spend_usd,
            "wall_time": limits.wall_seconds,
        }[run.limit]
        message = f"limit: {run.limit} ({cap})"
        return _error_body_text("limit", message, run, outcome), False, "limit"
    if status != "ok":
        kind = _STATUS_KIND.get(status, "exception")
        message = outcome.exception or f"script ended: {status}"
        extra: dict[str, Any] = {}
        if status == "exception" and run.has_value:
            extra["last_result_shape"] = _shape(run.last_value)
        return _error_body_text(kind, message, run, outcome, **extra), False, kind
    text = _dumps(outcome.value)
    if len(text) > limits.max_result_chars:
        text = text[: limits.max_result_chars] + _TRUNCATED
        script["limit"] = "result_size"
    return text, True, None


def _error_body_text(
    kind: str, message: str, run: _Run, outcome: ScriptOutcome, **extra: Any
) -> str:
    lines = (outcome.stderr_tail or "").splitlines()[-_STDERR_LINES:]
    return _dumps(
        _error_body(kind, message, run, stderr_tail="\n".join(lines), **extra)
    )


async def run_script_step(
    agent: BaseAgent,
    args: dict[str, Any],
    ctx: AgentContext,
    call_id: str,
    deps: dict[str, Any],
    names: list[str],
    iteration: int = -1,
) -> ScriptStepResult:
    """Run one `run_tool_script` call and return the step with its inner calls.

    `call_id` is the model's id for the call; proposals run later as ordinary calls.
    """
    from ze_agents.base_agent import (
        _finish,
        _hide_deps,
        _merge_deps,
        _model_args,
    )
    from ze_agents.script_stub import build_stub, source_hash
    from ze_agents.tool import get_tool

    started = time.monotonic()
    step_id = uuid4().hex
    turn = ScriptContext(
        user_turn=ctx.prompt, message_id=None, thread_id=ctx.session_id
    )
    runner = ctx.script_runner
    limits = getattr(runner, "limits", None) or ScriptLimits()

    source, procedure_id, kind, message = _resolve_source(args, ctx)
    shown = (source or "")[: limits.max_source_chars]
    script: dict[str, Any] = {
        "source": shown,
        "source_cut": bool(source) and len(source) > limits.max_source_chars,
        "outcome": "",
        "limit": None,
        "source_hash": source_hash(source) if source else "",
        "procedure_id": procedure_id,
        "model_call_id": _SAFE_ID.sub("_", call_id)[:_MAX_ID],
    }
    step_args: dict[str, Any] = (
        {"procedure_id": procedure_id}
        if procedure_id
        else {"source_hash": script["source_hash"]}
    )
    if kind is not None or source is None:
        return _failed_step(
            step_id, started, step_args, script, kind or "bad_request", message
        )
    if len(source) > limits.max_source_chars:
        return _failed_step(
            step_id,
            started,
            step_args,
            script,
            "source_too_long",
            f"source is over {limits.max_source_chars} characters",
        )

    read_names = data_read_names(agent, ctx, names)
    stub = build_stub([_hide_deps(get_tool(n).llm_schema(), deps) for n in read_names])
    run = _Run(step_id=step_id)
    budget = ScriptBudget(limit_usd=limits.max_spend_usd)
    allowed = set(read_names)
    writable = _writable_names(agent, ctx, names)

    def _refuse(req: ScriptRequest, error: str) -> DispatchReply:
        call = _refused(agent, step_id, req.tool, req.args, error)
        _finish(ctx, call)
        run.inner.append(call)
        return DispatchReply(ok=False, error=error)

    async def dispatch(req: ScriptRequest) -> DispatchReply:
        if run.requests >= limits.max_inner_calls:
            run.limit = "inner_calls"
            return DispatchReply(ok=False, error="limit: inner_calls", stop=True)
        if budget.exhausted:
            run.limit = "spend"
            return DispatchReply(ok=False, error="limit: spend", stop=True)
        run.requests += 1
        if not isinstance(req.tool, str) or not isinstance(req.args, dict):
            return _refuse(req, "bad_request")
        name = req.tool
        if name not in allowed:
            return _refuse(
                req,
                "writes_must_be_proposed" if name in writable else "tool_not_available",
            )
        model_args = _model_args(name, req.args)
        merged = _merge_deps(name, model_args, {**deps, "ctx": ctx})
        budget_token = current_script_budget.set(budget)
        flag_token = in_script_call.set(True)
        try:
            call = await agent.call_tool(
                name,
                ctx,
                _iteration=iteration,
                _lm_args=model_args,
                _call_id=uuid4().hex,
                **merged,
            )
        except AgentAbortedError:
            raise
        except Exception as exc:
            call = _refused(agent, step_id, name, model_args, str(exc))
            _finish(ctx, call)
            run.inner.append(call)
            return DispatchReply(ok=False, error=str(exc))
        finally:
            in_script_call.reset(flag_token)
            current_script_budget.reset(budget_token)
        call.parent_call_id = step_id
        run.inner.append(call)
        if not call.success:
            call.result = _cut_stored(call.result, limits.inner_result_store_chars)
            return DispatchReply(ok=False, error=call.error or "tool failed")
        value, error = _reply_value(call.result, limits.max_reply_bytes)
        call.result = _cut_stored(call.result, limits.inner_result_store_chars)
        if error is not None:
            return DispatchReply(ok=False, error=error)
        run.last_value, run.has_value = value, True
        return DispatchReply(ok=True, value=value)

    outcome = await runner.run(
        script_id=str(uuid4()),
        agent=agent.name,
        source=source,
        stub=stub,
        limits=limits,
        dispatch=dispatch,
        procedure_id=procedure_id,
        context=turn,
    )
    text, success, error_kind = _model_text(outcome, run, limits, script)
    script["outcome"] = outcome.status
    step = ToolCall(
        agent=agent.name,
        tool_name=SCRIPT_TOOL_NAME,
        args=step_args,
        result=text,
        duration_ms=int((time.monotonic() - started) * 1000),
        success=success,
        error=error_kind,
        call_id=step_id,
        started_at=started,
        inner_calls=run.inner,
        script=script,
    )
    proposals: list[ScriptProposal] = []
    if success and outcome.writes:
        proposals = _validate_writes(
            agent, ctx, names, list(outcome.writes), limits, step_id
        )
    log.info(
        "script_step_done",
        agent=agent.name,
        status=outcome.status,
        inner_calls=len(run.inner),
        limit=script["limit"],
    )
    return ScriptStepResult(step, proposals)
