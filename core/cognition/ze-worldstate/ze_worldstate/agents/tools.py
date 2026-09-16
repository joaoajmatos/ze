from __future__ import annotations

from uuid import UUID

from ze_agents.tool import ToolAccess, tool
from ze_worldstate.errors import InvalidLoopTransitionError, LoopNotFoundError
from ze_worldstate.review import close_loop as review_close
from ze_worldstate.review import drop_loop as review_drop
from ze_worldstate.store import LoopStore
from ze_worldstate.types import LoopState

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
    description="Close an open loop by id after listing to find a unique title match.",
)
async def close_loop(loop_store: LoopStore, loop_id: str) -> dict:
    try:
        uid = UUID(loop_id)
    except ValueError:
        return {"error": f"Invalid loop ID: {loop_id!r}"}
    try:
        loop = await review_close(loop_store, uid)
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
)
async def drop_loop(loop_store: LoopStore, loop_id: str) -> dict:
    try:
        uid = UUID(loop_id)
    except ValueError:
        return {"error": f"Invalid loop ID: {loop_id!r}"}
    try:
        loop = await review_drop(loop_store, uid)
    except LoopNotFoundError:
        return {"error": f"No loop found with ID {loop_id}."}
    except InvalidLoopTransitionError as exc:
        return {"error": str(exc)}
    return {
        "id": str(loop.id),
        "title": loop.title,
        "state": loop.state.value,
    }
