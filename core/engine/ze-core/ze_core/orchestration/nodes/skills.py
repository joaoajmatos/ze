from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from ze_logging import get_logger
from ze_core.orchestration.state import AgentState

log = get_logger(__name__)


async def match_skills(state: AgentState, config: RunnableConfig) -> dict:
    """Match active skills to this turn's message and stage the result for downstream
    consumption: `AgentContext.active_skills`/`skill_tool_names` (instruction injection +
    tool narrowing, consumed by `BaseAgent`) and `skill_matches` on state (consumed by
    `record_trace` to build `MessageTrace.skills_used`).

    Reads the injected `SkillMatcher` from `config["configurable"]["skill_matcher"]`,
    mirroring `surface_loops`'s `loop_surfacer` injection — `ze_core` never imports
    `ze_skills` directly.

    Runs after `fetch_context` so `state["agent_context"]` already exists (built there);
    a no-op (returns `{}`) when no matcher is injected, no agent context is available yet,
    or no skill matched this turn.
    """
    matcher: Any = config["configurable"].get("skill_matcher")
    if matcher is None:
        return {}

    agent_context = state.get("agent_context")
    if agent_context is None:
        return {}

    prompt = state.get("image_caption") or state.get("prompt") or ""
    try:
        matches = await matcher.match(prompt)
    except Exception as exc:
        log.warning("skill_matching_error", error=str(exc))
        return {}

    if not matches:
        return {}

    agent_context.active_skills = [m.skill for m in matches]
    agent_context.skill_tool_names = _combined_tool_names(matches)

    log.info("skills_matched", count=len(matches))
    return {"agent_context": agent_context, "skill_matches": matches}


def _combined_tool_names(matches: list) -> list[str] | None:
    """Intersect every matched skill's `allowed_tools` together (FR-008 — a skill
    restriction only ever narrows). Skills with `allowed_tools=None` impose no
    restriction of their own and are skipped; if none of the matches specify an
    `allowed_tools`, the combined result is None (no narrowing requested this turn)."""
    restricted_sets = [
        set(m.skill.allowed_tools) for m in matches if m.skill.allowed_tools is not None
    ]
    if not restricted_sets:
        return None
    combined = restricted_sets[0]
    for s in restricted_sets[1:]:
        combined &= s
    return sorted(combined)
