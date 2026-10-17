from __future__ import annotations

from datetime import UTC, datetime

from langchain_core.runnables import RunnableConfig
from ze_agents.screen import ScreenContext
from ze_core.orchestration.state import AgentState
from ze_core.screen import build_screen_note
from ze_logging import get_logger

log = get_logger(__name__)


async def resolve_screen(state: AgentState, config: RunnableConfig) -> dict:
    """Build the screen note from the client's context before routing. Never fails the turn."""
    configurable = config["configurable"]
    ctx = configurable.get("screen_context")
    registry = configurable.get("screen_resolvers")
    if not isinstance(ctx, ScreenContext) or registry is None or ctx.is_empty:
        return {}
    try:
        resolution = await build_screen_note(ctx, registry, datetime.now(UTC))
    except Exception as exc:
        log.warning("resolve_screen_failed", error=repr(exc))
        return {}
    if resolution.note is None:
        return {}
    return {
        "screen_note": resolution.note,
        "screen_subject_line": resolution.subject_line,
        "screen_trace": {
            "note_chars": resolution.note_chars,
            "resolvers": [
                {"kind": r.kind, "id": r.id, "status": r.status.value, "ms": r.ms}
                for r in resolution.rows
            ],
        },
    }
