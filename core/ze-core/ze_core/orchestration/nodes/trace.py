from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from ze_core.conversation.messages.types import (
    CompactionTrace,
    MemoryChunkTrace,
    MessageTrace,
    SkillUsageTrace,
    ToolCallTrace,
    WorkspaceUsageTrace,
)
from ze_core.orchestration.state import AgentState


_MAX_MEMORY_CHUNKS = 10
_WORKSPACE_TOOL_NAMES = frozenset(
    {
        "workspace_list",
        "workspace_read",
        "workspace_write",
        "workspace_delete",
        "workspace_run",
        "workspace_run_skill_script",
        "ingest_workspace_file",
    }
)


async def record_trace(state: AgentState, config: RunnableConfig) -> dict:
    envelope = state.get("envelope")
    agent_result = state.get("agent_result")

    if envelope is None:
        return {}

    memory_chunks = _extract_memory_chunks(state.get("memory_context"))
    tool_calls = _extract_tool_calls(agent_result)
    total_duration_ms = sum(t.duration_ms for t in tool_calls)

    subtask_agents = (
        [envelope.primary_agent]
        if not envelope.is_compound
        else [s.agent for s in envelope.subtasks]
    )

    compaction_span = state.get("compaction_span")
    compaction = (
        CompactionTrace(span_start=0, span_end=compaction_span[1])
        if compaction_span is not None
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
        total_duration_ms=total_duration_ms,
        compaction=compaction,
        resume_recap_applied=bool(state.get("resume_recap_applied")),
        skills_used=_extract_skills_used(state.get("skill_matches"), agent_result),
        workspace=await _extract_workspace(agent_result, config),
    )
    return {"message_trace": trace}


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

    mode = "ask"
    configurable = (config or {}).get("configurable") or {}
    store = configurable.get("workspace_store")
    if store is not None:
        try:
            stored_mode = await store.get_mode()
            mode = stored_mode.value if hasattr(stored_mode, "value") else str(stored_mode)
        except Exception:
            pass

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
            runs.append(
                {
                    "command": args.get("command", ""),
                    "success": bool(getattr(call, "success", False)),
                }
            )
        if name == "workspace_run_skill_script" and getattr(call, "success", False):
            script_ran = True

    return WorkspaceUsageTrace(
        mode=mode,
        runs=runs,
        files=files,
        script_ran=script_ran,
        unavailable=unavailable,
        planned=planned or None,
    )


def _extract_memory_chunks(memory_context: Any) -> list[MemoryChunkTrace]:
    if memory_context is None:
        return []

    chunks: list[MemoryChunkTrace] = []

    facts = getattr(memory_context, "facts", []) or []
    for fact in facts[:5]:
        text = f"{fact.predicate}: {fact.value}"
        chunks.append(
            MemoryChunkTrace(
                text=text[:300],
                score=getattr(fact, "relevance_score", None) or 0.0,
                source="fact",
                extraction_confidence=getattr(fact, "confidence", None),
            )
        )

    episodes = getattr(memory_context, "episodes", []) or []
    for ep in episodes[:5]:
        text = getattr(ep, "summary", None) or (
            ep.response[:300] if hasattr(ep, "response") else ""
        )
        chunks.append(
            MemoryChunkTrace(
                text=text[:300],
                score=getattr(ep, "relevance_score", None) or 0.0,
                source="episode",
            )
        )

    return chunks[:_MAX_MEMORY_CHUNKS]


def _extract_tool_calls(agent_result: Any) -> list[ToolCallTrace]:
    if agent_result is None:
        return []
    raw_calls = getattr(agent_result, "tool_calls", []) or []
    result = []
    for tc in raw_calls:
        raw_result = getattr(tc, "result", "") or ""
        snippet = str(raw_result)[:200] if raw_result else ""
        result.append(
            ToolCallTrace(
                name=getattr(tc, "tool_name", "unknown"),
                result_snippet=snippet,
                duration_ms=getattr(tc, "duration_ms", 0),
                success=getattr(tc, "success", True),
            )
        )
    return result
