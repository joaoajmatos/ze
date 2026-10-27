from __future__ import annotations

from uuid import UUID

from ze_agents.errors import ZeError
from ze_logging import get_logger
from ze_agents.tool import Injected, ToolAccess, tool, undo_payload
from ze_agents.reversibility import ToolReversibility
from ze_worldstate.errors import InvalidLoopTransitionError, LoopNotFoundError
from ze_worldstate.lifecycle import LoopLifecycle
from ze_worldstate.store import LoopStore
from ze_worldstate.tracking import LoopTracker
from ze_worldstate.types import LoopState, TrackOutcome

log = get_logger(__name__)

_OPEN = (
    LoopState.SUSPECTED.value,
    LoopState.ACTIVE.value,
    LoopState.DRIFTING.value,
)


@tool(
    access=ToolAccess.READ,
    description="List non-terminal open loops (title, id, state).",
)
async def list_open_loops(loop_store: LoopStore) -> list:
    loops = await loop_store.list(states=list(_OPEN))
    return [
        {
            "id": str(loop.id),
            "title": loop.title,
            "state": (
                loop.state.value if hasattr(loop.state, "value") else str(loop.state)
            ),
        }
        for loop in loops
        if loop.id is not None
    ]


@tool(
    access=ToolAccess.WRITE,
    description=(
        "Start tracking an open loop the user explicitly asked you to keep in mind "
        "(e.g. 'keep that on my radar'). `title` is a short phrase in the user's "
        "language naming the matter, under ten words. Pass `window_days` only if the "
        "user named a timeframe, as whole days; otherwise leave it 0. Call once per "
        "distinct concern. Only tell the user it is tracked if this returned ok true."
    ),
    reversibility=ToolReversibility.REVERSIBLE,
    undo_tool="drop_loop",
    undo_note=(
        "Dropping removes the loop from your radar, including an existing loop "
        "that was only reinforced."
    ),
    effect_phrase="started tracking an open loop",
)
async def track_loop(
    loop_tracker: LoopTracker,
    title: str,
    window_days: int = 0,
    session_id: Injected[str | None] = None,
) -> dict:
    try:
        result = await loop_tracker.track(title, window_days, session_id)
    except ZeError as exc:
        return {"ok": False, "error": str(exc) or "could not track the loop"}
    if not result.ok or result.loop is None:
        return {"ok": False, "error": result.error or "could not track the loop"}
    out = {
        "ok": True,
        "outcome": result.outcome,
        "id": str(result.loop.id),
        "title": result.loop.title,
        "state": result.loop.state.value,
    }
    if result.outcome == TrackOutcome.CREATED:
        out["undo"] = undo_payload(loop_id=str(result.loop.id))
    return out


@tool(
    access=ToolAccess.WRITE,
    description=(
        "Confirm a suspected open loop by id after listing, when the user says to "
        "keep track of it. Only tell the user it is tracked if this returned ok true."
    ),
    reversibility=ToolReversibility.REVERSIBLE,
    undo_tool="drop_loop",
    undo_note="Dropping the loop removes it; it does not return it to suspected.",
    effect_phrase="confirmed an open loop",
)
async def confirm_loop(lifecycle: LoopLifecycle, loop_id: str) -> dict:
    try:
        uid = UUID(loop_id)
    except ValueError:
        return {"ok": False, "error": f"Invalid loop ID: {loop_id!r}"}
    try:
        loop = await lifecycle.confirm(uid)
    except LoopNotFoundError:
        return {"ok": False, "error": f"No loop found with ID {loop_id}."}
    except InvalidLoopTransitionError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:
        log.warning("confirm_loop_failed", loop_id=loop_id, error=str(exc))
        return {"ok": False, "error": "could not confirm the loop"}
    return {
        "ok": True,
        "id": str(loop.id),
        "title": loop.title,
        "state": loop.state.value,
        "undo": undo_payload(loop_id=str(loop.id)),
    }


@tool(
    access=ToolAccess.WRITE,
    description="Close an open loop by id after listing to find a unique title match.",
    reversibility=ToolReversibility.IRREVERSIBLE,
    effect_phrase="closed an open loop",
    asks_first=False,
    no_ask_reason="Bookkeeping the user asked for; `track_loop` re-opens the concern.",
)
async def close_loop(lifecycle: LoopLifecycle, loop_id: str) -> dict:
    try:
        uid = UUID(loop_id)
    except ValueError:
        return {"error": f"Invalid loop ID: {loop_id!r}"}
    try:
        loop = await lifecycle.close(uid)
    except LoopNotFoundError:
        return {"error": f"No loop found with ID {loop_id}."}
    except InvalidLoopTransitionError as exc:
        return {"error": str(exc)}
    return {
        "id": str(loop.id),
        "title": loop.title,
        "state": loop.state.value,
    }


@tool(
    access=ToolAccess.WRITE,
    description="Drop an open loop by id after listing to find a unique title match.",
    reversibility=ToolReversibility.IRREVERSIBLE,
    effect_phrase="dropped an open loop",
    asks_first=False,
    no_ask_reason="Bookkeeping the user asked for; `track_loop` re-opens the concern.",
)
async def drop_loop(lifecycle: LoopLifecycle, loop_id: str) -> dict:
    try:
        uid = UUID(loop_id)
    except ValueError:
        return {"error": f"Invalid loop ID: {loop_id!r}"}
    try:
        loop = await lifecycle.drop(uid)
    except LoopNotFoundError:
        return {"error": f"No loop found with ID {loop_id}."}
    except InvalidLoopTransitionError as exc:
        return {"error": str(exc)}
    return {
        "id": str(loop.id),
        "title": loop.title,
        "state": loop.state.value,
    }
