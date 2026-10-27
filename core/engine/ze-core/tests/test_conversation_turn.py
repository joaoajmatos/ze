from unittest.mock import AsyncMock, MagicMock

import pytest

from ze_core.orchestration.state import AgentState
from ze_core.conversation import (
    TurnResult,
    invoke_raw_turn,
    make_graph_input,
    resume_turn,
)
from ze_agents.interface.types import RawInput
from ze_agents.park import ConfirmItem, WriteConfirmation


def test_graph_input_preserves_conversation_history():
    """messages/last_active_at must NOT be in the input dict: LangGraph input keys
    overwrite checkpointed channels, which would wipe history every turn and break
    follow-up questions."""
    graph_input = make_graph_input(RawInput(text="are these recent?"), "s1")
    assert "messages" not in graph_input
    assert "last_active_at" not in graph_input


async def _astream_events(events):
    for e in events:
        yield e


@pytest.fixture
def container():
    graph = MagicMock()
    graph.name = "LangGraph"
    graph.astream_events = lambda *a, **kw: _astream_events(
        [
            {
                "event": "on_chain_end",
                "name": "LangGraph",
                "data": {
                    "output": {
                        "final_response": "Done.",
                        "agent_result": None,
                        "envelope": None,
                        "error": None,
                    }
                },
            }
        ]
    )
    graph.aget_state = AsyncMock(return_value=MagicMock(next=()))

    c = MagicMock()
    c.graph = graph
    c.state_type = AgentState
    c.interface = None
    c._build_config = MagicMock(return_value={"configurable": {"thread_id": "42"}})
    return c


async def test_invoke_raw_turn_completed(container):
    outcome = await invoke_raw_turn(container, "42", RawInput(text="hello"))
    assert isinstance(outcome, TurnResult)
    assert outcome.interrupted is False
    assert outcome.response == "Done."


def _paused_state(confirmation):
    task = MagicMock()
    task.interrupts = [MagicMock(value=confirmation)]
    state = MagicMock(next=("await_write_confirmation",), interrupts=(), tasks=(task,))
    state.values = {"error": None}
    return state


def _confirmation():
    return WriteConfirmation(
        request_id="r1",
        kind="write",
        round=1,
        items=[ConfirmItem("i1", "calendar", "delete_event", "delete", "Dentist")],
    )


async def test_invoke_raw_turn_interrupted(container):
    confirmation = _confirmation()
    container.graph.aget_state.return_value = _paused_state(confirmation)
    container.graph.astream_events = lambda *a, **kw: _astream_events([])

    outcome = await invoke_raw_turn(container, "42", RawInput(text="delete my 3pm"))
    assert outcome.interrupted is True
    assert outcome.confirmation is confirmation
    assert outcome.response is None


async def test_resume_turn_sends_the_answer_as_a_command(container):
    container.graph.aget_state = AsyncMock(
        side_effect=[_paused_state(_confirmation()), MagicMock(next=())]
    )
    container.graph.ainvoke = AsyncMock(return_value={"final_response": "Deleted."})
    config = {"configurable": {"thread_id": "42"}}
    outcome = await resume_turn(container, config, resume={"choice": "approve"})
    assert outcome.response == "Deleted."
    command = container.graph.ainvoke.await_args.args[0]
    assert command.resume == {"choice": "approve"}


async def test_resume_turn_without_open_confirmation_does_nothing(container):
    container.graph.ainvoke = AsyncMock()
    outcome = await resume_turn(container, {"configurable": {"thread_id": "42"}})
    assert outcome.error == "No pending confirmation."
    container.graph.ainvoke.assert_not_awaited()


async def test_invoke_raw_turn_sets_cost_context_for_the_graph(container):
    from ze_core.telemetry.context import get_cost_context

    seen = []
    original = container.graph.astream_events

    def _spy(*a, **kw):
        seen.append(get_cost_context())
        return original(*a, **kw)

    container.graph.astream_events = _spy
    await invoke_raw_turn(container, "42", RawInput(text="hello"))

    assert seen[0].flow_type == "user_message"
    assert seen[0].session_id == "42"
