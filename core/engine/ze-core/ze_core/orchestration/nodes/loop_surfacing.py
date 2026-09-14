from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from ze_logging import get_logger
from ze_core.orchestration.state import AgentState

log = get_logger(__name__)


async def surface_loops(state: AgentState, config: RunnableConfig) -> dict:
    surfacer: Any = config["configurable"].get("loop_surfacer")
    if surfacer is None:
        return {}

    entity_ids = _extract_seeds(state.get("memory_context"))
    if not entity_ids:
        return {}

    try:
        mentions = await surfacer.inline_candidates(entity_ids)
    except Exception as exc:
        log.warning("inline_loop_surfacing_error", error=str(exc))
        return {}

    if not mentions:
        return {}

    component = _build_component(mentions)
    existing_components = list(state.get("components") or [])

    envelope = state.get("envelope")
    result = state.get("agent_result")
    is_compound = bool(envelope and envelope.is_compound and state.get("subtask_results"))
    updates: dict = {
        "drifting_loop_mentions": mentions,
        "components": existing_components + [component],
    }
    if not is_compound and result is not None:
        updates["final_response"] = (
            result.response + "\n\n" + _format_text_section(mentions)
        )

    log.info("inline_loop_surfacing_complete", mentions=len(mentions))
    return updates


def _extract_seeds(memory_context: Any) -> list:
    if memory_context is None:
        return []
    entities = getattr(memory_context, "entities", []) or []
    return [e.id for e in entities if e.id is not None]


def _build_component(mentions: list) -> dict:
    return {
        "type": "drifting_loops",
        "title": "Still open",
        "loops": [
            {
                "id": m.loop_id,
                "title": m.title,
                "mention_text": m.mention_text,
            }
            for m in mentions
        ],
    }


def _format_text_section(mentions: list) -> str:
    lines = ["---"]
    for m in mentions:
        lines.append(m.mention_text)
    return "\n".join(lines).rstrip()
