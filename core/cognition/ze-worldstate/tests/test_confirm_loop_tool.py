from __future__ import annotations

from ze_agents.tool import undo_payload
from uuid import uuid4

from ze_agents.reversibility import ToolReversibility
from ze_agents.tool import ToolAccess, get_tool, validate_tool_declarations
from ze_worldstate.errors import InvalidLoopTransitionError, LoopNotFoundError
from ze_worldstate.types import DECLARED_CONFIDENCE, LoopState, OpenLoop

import ze_worldstate.agents.tools  # noqa: F401  (registers the tools at import time)


class FakeStore:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.stamped: list[tuple] = []
        self.loop = OpenLoop(
            id=uuid4(),
            title="Switch bank",
            provenance="email",
            confidence=0.35,
            state=LoopState.ACTIVE,
        )

    async def transition(self, loop_id, state, **kwargs):
        if self.error is not None:
            raise self.error
        return self.loop

    async def resolve(self, loop_id, evidence):
        return self.loop

    async def stamp_declared(self, loop_id, *, confidence, deadline):
        self.stamped.append((loop_id, confidence, deadline))


def test_confirm_loop_declaration():
    spec = get_tool("confirm_loop")

    assert spec.access is ToolAccess.WRITE
    assert spec.reversibility is ToolReversibility.REVERSIBLE
    assert spec.undo_tool == "drop_loop"
    assert spec.undo_note
    assert spec.effect_phrase == "confirmed an open loop"
    validate_tool_declarations()


async def test_success_confirms_and_stamps():
    store = FakeStore()

    out = await get_tool("confirm_loop").func(loop_store=store, loop_id=str(uuid4()))

    assert out == {
        "ok": True,
        "id": str(store.loop.id),
        "title": "Switch bank",
        "state": "active",
        "undo": undo_payload(loop_id=str(store.loop.id)),
    }
    assert store.stamped[0][1] == DECLARED_CONFIDENCE


async def test_bad_uuid():
    out = await get_tool("confirm_loop").func(loop_store=FakeStore(), loop_id="nope")

    assert out == {"ok": False, "error": "Invalid loop ID: 'nope'"}


async def test_not_found():
    loop_id = str(uuid4())
    store = FakeStore(error=LoopNotFoundError("x"))

    out = await get_tool("confirm_loop").func(loop_store=store, loop_id=loop_id)

    assert out == {"ok": False, "error": f"No loop found with ID {loop_id}."}


async def test_not_suspected():
    store = FakeStore(error=InvalidLoopTransitionError("Loop is already active"))

    out = await get_tool("confirm_loop").func(loop_store=store, loop_id=str(uuid4()))

    assert out == {"ok": False, "error": "Loop is already active"}
    assert store.stamped == []


async def test_unexpected_error_is_generic():
    store = FakeStore(error=RuntimeError("db exploded"))

    out = await get_tool("confirm_loop").func(loop_store=store, loop_id=str(uuid4()))

    assert out == {"ok": False, "error": "could not confirm the loop"}
