from __future__ import annotations

import re
import time
from dataclasses import replace
from typing import Any

from langchain_core.runnables import RunnableConfig

from ze_agents.delegate import DELEGATE_TOOL_NAME
from ze_agents.effects import effect_imperative, ensure_declined_lines
from ze_agents.errors import UnknownToolError
from ze_agents.park import generic_summary
from ze_agents.tool import get_tool
from ze_agents.types import Source, add_sources
from ze_core.conversation.messages.memory_chunks import extract_memory_chunks
from ze_core.conversation.messages.types import (
    CompactionTrace,
    InputTrace,
    MessageTrace,
    ProcedureUsageTrace,
    ScriptTrace,
    RoutingScore,
    RoutingThresholds,
    ScreenTrace,
    SkillUsageTrace,
    SourceTrace,
    ToolCallTrace,
    WorkspaceUsageTrace,
)
from ze_core.orchestration.child_runs import turn_ledger
from ze_core.orchestration.loop_offer import with_loop_offer_line
from ze_core.orchestration.promote import ledger_with_promote_offer
from ze_core.orchestration.state import AgentState
from ze_core.telemetry.turn import current_turn_telemetry
from ze_logging import get_logger

log = get_logger(__name__)


ROUTING_SCORES_SHOWN = 9  # matches system_one routing shortlist_k

_STILL_RUNNING_ID_PATTERN = re.compile(r"^\[still running\] run ([^:]+):")

_WORKSPACE_TOOL_NAMES = frozenset(
    {
        "workspace_list",
        "workspace_read",
        "workspace_write",
        "workspace_delete",
        "workspace_run",
        "workspace_run_skill_script",
        "ingest_workspace_file",
        "workspace_reset",
    }
)


async def record_trace(state: AgentState, config: RunnableConfig) -> dict:
    envelope = state.get("envelope")
    agent_result = state.get("agent_result")

    if envelope is None:
        return {}

    memory_chunks = extract_memory_chunks(state.get("memory_context"))
    tool_calls = _extract_tool_calls(
        agent_result,
        list(state.get("subtask_results") or []),
        current_turn_telemetry.get(),
    )
    tool_duration_ms = sum(t.duration_ms for t in tool_calls)

    subtask_agents = (
        [envelope.primary_agent]
        if not envelope.is_compound
        else [s.agent for s in envelope.subtasks]
    )

    # What the prompt was built from: fetch_context blanks the history after a
    # resume gap, while state["messages"] still holds it.
    ctx = state.get("agent_context")
    history = (ctx.messages if ctx is not None else state.get("messages")) or []
    opening = history[0] if history else {}
    compaction = (
        CompactionTrace(span_start=0, span_end=opening["compaction_span"][1])
        if opening.get("compaction_summary") and opening.get("compaction_span")
        else None
    )

    trace = MessageTrace(
        agent=envelope.primary_agent,
        routing_method=envelope.routing_method,
        confidence=envelope.confidence,
        score_gap=envelope.score_gap,
        is_compound=envelope.is_compound,
        subtasks=subtask_agents,
        memory_chunks=memory_chunks,
        tool_calls=tool_calls,
        tool_duration_ms=tool_duration_ms,
        compaction=compaction,
        resume_recap_applied=bool(state.get("resume_recap_applied")),
        loop_offer_ids=list(state.get("loop_offer_ids") or []),
        skills_used=_extract_skills_used(state.get("skill_matches"), agent_result),
        workspace=await _extract_workspace(agent_result, config),
        procedure=_extract_procedure(state),
        conductor_hint=state.get("conductor_hint"),
        conductor_ledger=ledger_with_promote_offer(turn_ledger(state)),
        judgments=list(state.get("judgments") or []),
        sources=_extract_sources(
            agent_result, list(state.get("subtask_results") or [])
        ),
        effects_known=True,
        write_confirmations=[
            *(dict(row) for row in state.get("write_outcomes") or []),
            *_refused_over_cap_rows(state, agent_result),
        ],
        tier=state.get("tier"),
        screen=_screen_trace(state.get("screen_trace")),
        routing_scores=_routing_scores(envelope),
        routing_thresholds=_routing_thresholds(envelope),
        input=_input_trace(state),
    )
    update: dict[str, Any] = {"message_trace": trace}
    update.update(_with_declined_lines(state, agent_result))
    offer_ids = list(state.get("loop_offer_ids") or [])
    if agent_result is not None and not state.get("error"):
        reply = (
            update.get("final_response")
            or state.get("final_response")
            or getattr(agent_result, "response", "")
            or ""
        )
        with_offer = with_loop_offer_line(
            reply,
            state.get("prompt") or "",
            offer_ids,
            history=list(state.get("messages") or []),
        )
        if with_offer != reply:
            update["final_response"] = with_offer
    return update


def _refused_over_cap_rows(
    state: AgentState, agent_result: Any
) -> list[dict[str, Any]]:
    """One row per asks-first call refused for being past the round cap (FR-029).

    No confirmation was opened for them, so `request_id` is empty; `round` is the
    round that would have been asked.
    """
    round_ = int(state.get("write_rounds") or 0) + 1
    refused: list[tuple[str, str, dict]] = []
    for result in [agent_result, *(state.get("subtask_results") or [])]:
        for call in getattr(result, "tool_calls", None) or []:
            if getattr(call, "gate", None) == "refused_over_cap":
                refused.append((result.agent, call.tool_name, call.args))
            if call.tool_name == DELEGATE_TOOL_NAME and isinstance(
                getattr(call, "result", None), dict
            ):
                for nested in call.result.get("tool_calls") or []:
                    if nested.get("gate") == "refused_over_cap":
                        refused.append(
                            (
                                str(call.args.get("agent") or ""),
                                nested.get("tool_name", ""),
                                nested.get("args") or {},
                            )
                        )
    return [
        {
            "request_id": "",
            "round": round_,
            "item_id": f"refused-{index}",
            "agent": agent,
            "tool": tool_name,
            "effect": _effect(tool_name),
            "summary": generic_summary(args),
            "outcome": "refused",
        }
        for index, (agent, tool_name, args) in enumerate(refused)
    ]


def _effect(tool_name: str) -> str | None:
    try:
        phrase = get_tool(tool_name).effect_phrase
    except UnknownToolError:
        return None
    return effect_imperative(phrase) if phrase else None


def _with_declined_lines(state: AgentState, agent_result: Any) -> dict[str, Any]:
    """Append "Okay, I didn't ..." for each declined item the reply leaves out."""
    rows = list(state.get("write_outcomes") or [])
    if not rows:
        return {}
    reply = state.get("final_response") or (
        agent_result.response if agent_result is not None else ""
    )
    fixed = ensure_declined_lines(reply or "", rows)
    if fixed == (reply or ""):
        return {}
    update: dict[str, Any] = {"final_response": fixed}
    if agent_result is not None and not state.get("final_response"):
        update["agent_result"] = replace(agent_result, response=fixed)
    return update


def _extract_sources(
    agent_result: Any, subtask_results: list[Any]
) -> list[SourceTrace]:
    found: list[Source] = []
    for result in [agent_result, *subtask_results]:
        add_sources(found, list(getattr(result, "sources", None) or []))
    return [SourceTrace(url=s.url, title=s.title) for s in found]


def _extract_skills_used(
    skill_matches: Any, agent_result: Any = None
) -> list[SkillUsageTrace]:
    if not skill_matches:
        return []
    script_ids = _script_ran_skill_ids(agent_result)
    result: list[SkillUsageTrace] = []
    for m in skill_matches:
        skill = getattr(m, "skill", None)
        if skill is None:
            continue
        source = getattr(skill, "source", None)
        trigger = getattr(m, "trigger", None)
        skill_id = str(getattr(skill, "id", ""))
        result.append(
            SkillUsageTrace(
                skill_id=skill_id,
                name=getattr(skill, "name", ""),
                source=source.value if hasattr(source, "value") else str(source),
                trigger=trigger.value if hasattr(trigger, "value") else str(trigger),
                similarity=getattr(m, "similarity", None),
                script_ran=skill_id in script_ids,
                below_floor=bool(getattr(m, "below_floor", False)),
            )
        )
    return result


def _script_ran_skill_ids(agent_result: Any) -> set[str]:
    ids: set[str] = set()
    for call in _iter_tool_calls(agent_result):
        if getattr(call, "tool_name", "") != "workspace_run_skill_script":
            continue
        if not getattr(call, "success", False):
            continue
        args = getattr(call, "args", None) or {}
        skill_id = args.get("skill_id")
        if skill_id:
            ids.add(str(skill_id))
    return ids


def _iter_tool_calls(agent_result: Any) -> list[Any]:
    if agent_result is None:
        return []
    return list(getattr(agent_result, "tool_calls", None) or [])


async def _extract_workspace(
    agent_result: Any, config: RunnableConfig
) -> WorkspaceUsageTrace | None:
    calls = [
        c
        for c in _iter_tool_calls(agent_result)
        if getattr(c, "tool_name", "") in _WORKSPACE_TOOL_NAMES
    ]
    if not calls:
        return None

    planned: list[str] = []
    files: list[dict[str, str]] = []
    runs: list[dict[str, Any]] = []
    unavailable = False
    script_ran = False
    for call in calls:
        name = getattr(call, "tool_name", "")
        args = getattr(call, "args", None) or {}
        result = str(getattr(call, "result", "") or "")
        error = str(getattr(call, "error", "") or "")
        blob = f"{result} {error}".lower()
        if "unavailable" in blob:
            unavailable = True
        if result.startswith("[plan]"):
            planned.append(result)
        path = args.get("path")
        if path and name in {
            "workspace_write",
            "workspace_read",
            "workspace_delete",
            "ingest_workspace_file",
        }:
            op = {
                "workspace_write": "write",
                "workspace_read": "read",
                "workspace_delete": "delete",
                "ingest_workspace_file": "ingest",
            }[name]
            files.append({"path": str(path), "op": op})
        if name == "workspace_run":
            run_entry: dict[str, Any] = {
                "command": args.get("command", ""),
                "success": bool(getattr(call, "success", False)),
            }
            if result.startswith("[still running]"):
                # Trace-only projection for a detached (ended_at IS NULL) row —
                # never written to workspace_runs.status, which stays one of
                # WorkspaceRunStatus's five closed terminal values.
                run_entry["status"] = "in_progress"
                # The handle is already embedded in the tool's reply text
                # (ze_workspace/tools.py) — surfaced here so Phase 131's live
                # output view has something to open the watch stream with.
                id_match = _STILL_RUNNING_ID_PATTERN.match(result)
                if id_match:
                    run_entry["id"] = id_match.group(1)
            runs.append(run_entry)
        if name == "workspace_run_skill_script" and getattr(call, "success", False):
            script_ran = True

    return WorkspaceUsageTrace(
        runs=runs,
        files=files,
        script_ran=script_ran,
        unavailable=unavailable,
        planned=planned or None,
    )


def _routing_scores(envelope: Any) -> list[RoutingScore]:
    raw = getattr(envelope, "raw_scores", None) or {}
    if len(raw) <= 1:
        return []
    ranked = sorted(raw.items(), key=lambda item: item[1], reverse=True)
    return [
        RoutingScore(agent=agent, score=float(score))
        for agent, score in ranked[:ROUTING_SCORES_SHOWN]
    ]


def _routing_thresholds(envelope: Any) -> RoutingThresholds | None:
    threshold = getattr(envelope, "threshold", None)
    gap = getattr(envelope, "gap_threshold", None)
    if threshold is None or gap is None:
        return None
    return RoutingThresholds(threshold=float(threshold), gap=float(gap))


def _start_offset_ms(started_at: float | None, recorder: Any) -> int | None:
    """Offset of a tool start from the turn start, or None when it cannot be trusted.

    A partial recorder was recreated after a restart, so its monotonic base differs
    from the run-1 `started_at` values that were checkpointed.
    """
    if started_at is None or recorder is None or getattr(recorder, "partial", False):
        return None
    base = getattr(recorder, "started", None)
    if base is None:
        return None
    now = time.monotonic()
    if not base <= started_at <= now:
        return None
    return round((started_at - base) * 1000)


def _extract_tool_calls(
    agent_result: Any,
    subtask_results: list[Any] | None = None,
    recorder: Any = None,
) -> list[ToolCallTrace]:
    """Resolve every call (nested delegate calls flattened) against the registry now,
    so retry eligibility never depends on registry state at retry time."""
    results = [r for r in [agent_result, *(subtask_results or [])] if r is not None]
    if not results:
        return []
    from ze_agents.delegate import DELEGATE_TOOL_NAME
    from ze_agents.nested_tools import flatten_tool_calls
    from ze_agents.scripts import SCRIPT_TOOL_NAME
    from ze_agents.tool import ToolAccess, registered_tools

    registry = registered_tools()
    result = []
    top_level = [c for r in results for c in (getattr(r, "tool_calls", None) or [])]
    for call_index, tc in enumerate(flatten_tool_calls(top_level)):
        name = getattr(tc, "tool_name", "unknown")
        raw_result = getattr(tc, "result", "") or ""
        snippet = str(raw_result)[:200] if raw_result else ""
        spec = registry.get(name)
        if name == DELEGATE_TOOL_NAME:
            access = "delegate"
        elif name == SCRIPT_TOOL_NAME:
            access = (
                "script"  # the step reads nothing itself; its calls are their own rows
            )
        elif name.startswith("openrouter:"):
            access = "read"  # OpenRouter server tools (web search) only read
        elif spec is None:
            access = "unknown"
        else:
            access = "write" if spec.access is ToolAccess.WRITE else "read"
        gate = getattr(tc, "gate", "none")
        result.append(
            ToolCallTrace(
                name=name,
                result_snippet=snippet,
                duration_ms=getattr(tc, "duration_ms", 0),
                success=getattr(tc, "success", True),
                access=access,
                reversibility=(
                    spec.reversibility.value
                    if spec is not None and spec.reversibility is not None
                    else None
                ),
                undo_tool=spec.undo_tool if spec is not None else None,
                gate=gate,
                effect_phrase=spec.effect_phrase if spec is not None else None,
                agent=getattr(tc, "agent", None),
                undo_args=getattr(tc, "undo", None),
                undo_note=spec.undo_note if spec is not None else None,
                call_index=call_index,
                call_id=getattr(tc, "call_id", ""),
                start_offset_ms=_start_offset_ms(
                    getattr(tc, "started_at", None), recorder
                ),
                parent_call_id=getattr(tc, "parent_call_id", None),
                script=_script_trace(getattr(tc, "script", None)),
            )
        )
    return result


def _script_trace(raw: Any) -> ScriptTrace | None:
    if not isinstance(raw, dict):
        return None
    return ScriptTrace(
        source=str(raw.get("source") or ""),
        source_cut=bool(raw.get("source_cut")),
        outcome=str(raw.get("outcome") or ""),
        limit=raw.get("limit"),
        source_hash=str(raw.get("source_hash") or ""),
        procedure_id=raw.get("procedure_id"),
    )


def _extract_procedure(state: AgentState) -> ProcedureUsageTrace | None:
    from ze_core.orchestration.procedure_activation import procedure_usage_trace

    payload = procedure_usage_trace(state)
    if payload is None:
        return None
    return ProcedureUsageTrace(**payload)


def _screen_trace(raw: Any) -> ScreenTrace | None:
    if not isinstance(raw, dict):
        return None
    try:
        return ScreenTrace.from_dict(raw)
    except (TypeError, ValueError):
        log.warning("screen_trace_unreadable")
        return None


def _input_trace(state: AgentState) -> InputTrace | None:
    voice = state.get("voice_input")
    if not voice:
        return None
    return InputTrace(
        modality="voice",
        duration_s=voice.get("duration_s"),
        edited=voice.get("edited"),
    )
