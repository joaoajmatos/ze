from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from ze_logging import get_logger
from ze_core.orchestration.state import AgentState

log = get_logger(__name__)


async def surface_loops(state: AgentState, config: RunnableConfig) -> dict:
    surfacer: Any = config["configurable"].get("turn_surfacer")
    if surfacer is None:
        return {}

    prompt = state.get("prompt") or ""
    if getattr(surfacer, "is_global_open_query", lambda _p: False)(prompt):
        return {}

    memory_context = state.get("memory_context")
    entity_ids, entities = _extract_entities(memory_context)
    if not entity_ids:
        return {}

    try:
        mentions = await surfacer.inline_mentions(entity_ids, entities=entities)
    except Exception as exc:
        log.warning("inline_turn_surfacing_error", error=str(exc))
        return {}

    if not mentions:
        return {}

    component = _build_component(mentions)
    existing_components = list(state.get("components") or [])

    envelope = state.get("envelope")
    result = state.get("agent_result")
    is_compound = bool(
        envelope and envelope.is_compound and state.get("subtask_results")
    )
    updates: dict = {
        "open_item_mentions": mentions,
        "components": existing_components + [component],
    }
    if not is_compound and result is not None:
        updates["final_response"] = (
            result.response + "\n\n" + _format_text_section(mentions)
        )

    log.info("inline_turn_surfacing_complete", mentions=len(mentions))
    return updates


def _extract_entities(memory_context: Any) -> tuple[list, list]:
    if memory_context is None:
        return [], []
    entities = list(getattr(memory_context, "entities", []) or [])
    entity_ids = [e.id for e in entities if getattr(e, "id", None) is not None]
    return entity_ids, entities


def _build_component(mentions: list) -> dict:
    return {
        "type": "open_items",
        "title": "Still open",
        "items": [
            {
                "id": m.source_id,
                "source_kind": m.source_kind,
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
