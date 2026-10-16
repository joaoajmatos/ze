"""resume_turn answers only the confirmation it names (Phase 181, review H4)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from ze_agents.park import WriteConfirmation
from ze_core.conversation.turn import NO_PENDING_CONFIRMATION, resume_turn

CONFIG = {"configurable": {"thread_id": "t1"}}


def _container(open_id: str) -> SimpleNamespace:
    paused = SimpleNamespace(
        interrupts=[SimpleNamespace(value=WriteConfirmation(open_id, "write", 1))],
        tasks=(),
        next=(),
        values={},
    )
    graph = SimpleNamespace(
        aget_state=AsyncMock(return_value=paused),
        ainvoke=AsyncMock(return_value={"final_response": "Done."}),
    )
    return SimpleNamespace(graph=graph)


async def test_a_different_request_id_does_not_resume() -> None:
    container = _container("new")

    result = await resume_turn(
        container, CONFIG, {"choice": "approve"}, request_id="old"
    )

    assert result.error == NO_PENDING_CONFIRMATION
    container.graph.ainvoke.assert_not_awaited()


async def test_the_open_request_id_resumes() -> None:
    container = _container("new")

    result = await resume_turn(
        container, CONFIG, {"choice": "approve"}, request_id="new"
    )

    assert result.error is None
    container.graph.ainvoke.assert_awaited_once()
