from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

from ze_agents.tool import undo_payload

from ze_agents.reversibility import ToolReversibility
from ze_agents.tool import ToolAccess, get_tool, validate_tool_declarations
from ze_worldstate.errors import InvalidLoopTransitionError, LoopNotFoundError
from ze_worldstate.lifecycle import DeclaredStamp, LoopLifecycle
from ze_worldstate.types import LoopState, OpenLoop

import ze_worldstate.agents.tools  # noqa: F401  (registers the tools at import time)


def _loop() -> OpenLoop:
    return OpenLoop(
        id=uuid4(),
        title="Switch bank",
        provenance="email",
        confidence=DeclaredStamp.CONFIDENCE,
        state=LoopState.ACTIVE,
    )


def _lifecycle(error: Exception | None = None) -> AsyncMock:
    lifecycle = AsyncMock(spec=LoopLifecycle)
    if error is not None:
        lifecycle.confirm.side_effect = error
    else:
        lifecycle.confirm.return_value = _loop()
    return lifecycle


def test_confirm_loop_declaration():
    spec = get_tool("confirm_loop")

    assert spec.access is ToolAccess.WRITE
    assert spec.reversibility is ToolReversibility.REVERSIBLE
    assert spec.undo_tool == "drop_loop"
    assert spec.undo_note
    assert spec.effect_phrase == "confirmed an open loop"
    validate_tool_declarations()


async def test_success_confirms_through_the_lifecycle():
    lifecycle = _lifecycle()
    loop = lifecycle.confirm.return_value
    loop_id = uuid4()

    out = await get_tool("confirm_loop").func(lifecycle=lifecycle, loop_id=str(loop_id))

    assert out == {
        "ok": True,
        "id": str(loop.id),
        "title": "Switch bank",
        "state": "active",
        "undo": undo_payload(loop_id=str(loop.id)),
    }
    lifecycle.confirm.assert_awaited_once_with(loop_id)


async def test_lifecycle_is_the_only_dependency():
    params = get_tool("confirm_loop").llm_schema()["function"]["parameters"]

    assert list(params["properties"]) == ["loop_id"]


async def test_bad_uuid():
    lifecycle = _lifecycle()

    out = await get_tool("confirm_loop").func(lifecycle=lifecycle, loop_id="nope")

    assert out == {"ok": False, "error": "Invalid loop ID: 'nope'"}
    lifecycle.confirm.assert_not_awaited()


async def test_not_found():
    loop_id = str(uuid4())

    out = await get_tool("confirm_loop").func(
        lifecycle=_lifecycle(LoopNotFoundError("x")), loop_id=loop_id
    )

    assert out == {"ok": False, "error": f"No loop found with ID {loop_id}."}


async def test_not_suspected():
    out = await get_tool("confirm_loop").func(
        lifecycle=_lifecycle(InvalidLoopTransitionError("Loop is already active")),
        loop_id=str(uuid4()),
    )

    assert out == {"ok": False, "error": "Loop is already active"}


async def test_unexpected_error_is_generic():
    out = await get_tool("confirm_loop").func(
        lifecycle=_lifecycle(RuntimeError("db exploded")), loop_id=str(uuid4())
    )

    assert out == {"ok": False, "error": "could not confirm the loop"}


async def test_close_and_drop_go_through_the_lifecycle():
    lifecycle = AsyncMock(spec=LoopLifecycle)
    lifecycle.close.return_value = _loop()
    lifecycle.drop.return_value = _loop()
    loop_id = uuid4()

    closed = await get_tool("close_loop").func(
        lifecycle=lifecycle, loop_id=str(loop_id)
    )
    dropped = await get_tool("drop_loop").func(
        lifecycle=lifecycle, loop_id=str(loop_id)
    )

    assert closed["title"] == dropped["title"] == "Switch bank"
    lifecycle.close.assert_awaited_once_with(loop_id)
    lifecycle.drop.assert_awaited_once_with(loop_id)


async def test_close_and_drop_report_refusals():
    lifecycle = AsyncMock(spec=LoopLifecycle)
    lifecycle.close.side_effect = InvalidLoopTransitionError("nope")
    lifecycle.drop.side_effect = LoopNotFoundError("x")
    loop_id = str(uuid4())

    closed = await get_tool("close_loop").func(lifecycle=lifecycle, loop_id=loop_id)
    dropped = await get_tool("drop_loop").func(lifecycle=lifecycle, loop_id=loop_id)

    assert closed == {"error": "nope"}
    assert dropped == {"error": f"No loop found with ID {loop_id}."}
