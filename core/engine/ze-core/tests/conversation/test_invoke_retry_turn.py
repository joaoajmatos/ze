from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from ze_agents.errors import RetryFailedError, RetryRewindError
from ze_core.orchestration.state import AgentState
from ze_core.conversation import invoke_retry_turn

_OLD = uuid4()
HISTORY = [
    {"role": "user", "content": "q"},
    {"role": "assistant", "content": "old"},
]


async def _events(output):
    yield {
        "event": "on_chain_end",
        "name": "LangGraph",
        "data": {"output": output},
    }


def _container(output, *, history=None, next_=(), stream_error=None):
    graph = MagicMock()
    graph.name = "LangGraph"
    seen = {}

    def astream(graph_input, config, version):
        seen["config"] = config
        if stream_error:
            raise stream_error
        return _events(output)

    graph.astream_events = astream
    graph.aget_state = AsyncMock(
        side_effect=[
            MagicMock(
                values={"messages": list(HISTORY if history is None else history)}
            ),
            MagicMock(next=next_, values=output),
        ]
    )
    graph.aupdate_state = AsyncMock()
    c = MagicMock()
    c.graph = graph
    c.state_type = AgentState
    c.interface = None
    c._build_config = lambda tid, **extra: {"configurable": {"thread_id": tid, **extra}}
    return c, graph, seen


async def test_success_rewinds_runs_in_retry_mode_and_keeps_new_history():
    c, graph, seen = _container({"final_response": "new", "error": None})
    result = await invoke_retry_turn(c, "t1", "q", replaces=_OLD)
    assert result.response == "new"
    assert seen["config"]["configurable"]["retry_mode"] is True
    graph.aupdate_state.assert_awaited_once()
    assert graph.aupdate_state.await_args.args[1] == {"messages": []}


async def test_failure_restores_original_history():
    c, graph, _ = _container({}, stream_error=RuntimeError("boom"))
    with pytest.raises(RetryFailedError):
        await invoke_retry_turn(c, "t1", "q", replaces=_OLD)
    assert graph.aupdate_state.await_count == 2
    assert graph.aupdate_state.await_args.args[1] == {"messages": HISTORY}


async def test_error_state_restores_and_fails():
    c, graph, _ = _container({"final_response": None, "error": "bad"})
    with pytest.raises(RetryFailedError):
        await invoke_retry_turn(c, "t1", "q", replaces=_OLD)
    assert graph.aupdate_state.await_args.args[1] == {"messages": HISTORY}


async def test_empty_reply_restores_and_fails():
    c, graph, _ = _container({"final_response": "", "error": None})
    with pytest.raises(RetryFailedError):
        await invoke_retry_turn(c, "t1", "q", replaces=_OLD)
    assert graph.aupdate_state.await_args.args[1] == {"messages": HISTORY}


async def test_components_only_reply_is_a_valid_retry():
    c, _, _ = _container(
        {"final_response": "", "error": None, "components": [{"type": "table"}]}
    )
    result = await invoke_retry_turn(c, "t1", "q", replaces=_OLD)
    assert result.final_state["components"] == [{"type": "table"}]


async def test_config_carries_the_retry_identity():
    c, _, seen = _container({"final_response": "new", "error": None})
    await invoke_retry_turn(c, "t1", "q", replaces=_OLD)
    configurable = seen["config"]["configurable"]
    assert configurable["retry_mode"] is True
    assert configurable["retry_replaces"] == str(_OLD)


async def test_interrupt_is_returned_without_restoring_history():
    c, graph, _ = _container(
        {"final_response": "x"}, next_=("await_write_confirmation",)
    )
    result = await invoke_retry_turn(c, "t1", "q", replaces=_OLD)
    assert result.interrupted is True
    assert graph.aupdate_state.await_count == 1
    assert graph.aupdate_state.await_args.args[1] == {"messages": []}


async def test_unrewindable_history_raises_before_any_run():
    c, graph, seen = _container({}, history=[])
    with pytest.raises(RetryRewindError):
        await invoke_retry_turn(c, "t1", "q", replaces=_OLD)
    assert "config" not in seen
    graph.aupdate_state.assert_not_awaited()
