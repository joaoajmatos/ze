from __future__ import annotations

from datetime import UTC, datetime

from langchain_core.runnables import RunnableConfig
from ze_agents.screen import ScreenContext, sanitize_text
from ze_core.orchestration.state import AgentState
from ze_core.screen import build_screen_note
from ze_core.screen.note import kind_label
from ze_logging import get_logger

log = get_logger(__name__)


def _base_trace(ctx: ScreenContext, invalid: list[str]) -> dict:
    """The trace of what arrived, before anything is resolved. JSON-safe: it is checkpointed."""
    return {
        "origin": ctx.origin.value,
        "place": ctx.place,
        "route": ctx.route,
        "subject": [
            f"{kind_label(r.kind)} · {sanitize_text(r.label or r.id, 80)}"
            for r in ctx.subject
        ],
        "selection_count": len(ctx.selection),
        "visible_count": len(ctx.visible),
        "canvas_count": len(ctx.canvas),
        "focused_module": ctx.focused_module,
        "captured_at": ctx.captured_at.isoformat() if ctx.captured_at else None,
        "note_chars": 0,
        "invalid": invalid,
        "resolvers": [],
    }


async def resolve_screen(state: AgentState, config: RunnableConfig) -> dict:
    """Build the screen note from the client's context before routing. Never fails the turn."""
    configurable = config["configurable"]
    ctx = configurable.get("screen_context")
    ctx = ctx if isinstance(ctx, ScreenContext) else ScreenContext()
    invalid = [str(w) for w in configurable.get("screen_context_invalid") or []]
    if ctx.is_empty and not invalid:
        return {}
    trace = _base_trace(ctx, invalid)
    registry = configurable.get("screen_resolvers")
    if registry is None or ctx.is_empty:
        return {"screen_trace": trace}
    try:
        resolution = await build_screen_note(ctx, registry, datetime.now(UTC))
    except Exception as exc:
        log.warning("resolve_screen_failed", error=repr(exc))
        return {"screen_trace": trace}
    if resolution.note is None:
        return {"screen_trace": trace}
    trace["subject"] = resolution.subject_labels or trace["subject"]
    trace["note_chars"] = resolution.note_chars
    trace["resolvers"] = [
        {"kind": r.kind, "id": r.id, "status": r.status.value, "ms": r.ms}
        for r in resolution.rows
    ]
    return {
        "screen_note": resolution.note,
        "screen_subject_line": resolution.subject_line,
        "screen_trace": trace,
    }
