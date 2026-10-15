"""Spike for research R1: rewind a thread's checkpointed history before a retry.

Uses LangGraph's in-memory saver with a graph shaped like the real one (a node
that reads `messages`, then `write_memory` appends the exchange).
"""

from __future__ import annotations

from typing import TypedDict

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from ze_agents.errors import RetryRewindError
from ze_core.conversation.rewind import restore_messages, rewind_last_exchange


class _State(TypedDict, total=False):
    prompt: str
    messages: list[dict]
    seen: list[dict]
    reply: str


def _graph():
    async def respond(state: _State) -> dict:
        history = list(state.get("messages") or [])
        return {"seen": history, "reply": f"re:{state['prompt']}:{len(history)}"}

    async def write_memory(state: _State) -> dict:
        updated = list(state.get("messages") or []) + [
            {"role": "user", "content": state["prompt"]},
            {"role": "assistant", "content": state["reply"]},
        ]
        return {"messages": updated}

    b = StateGraph(_State)
    b.add_node("respond", respond)
    b.add_node("write_memory", write_memory)
    b.set_entry_point("respond")
    b.add_edge("respond", "write_memory")
    b.add_edge("write_memory", END)
    return b.compile(checkpointer=MemorySaver())


async def _turn(graph, config, prompt: str) -> dict:
    # Mirrors make_graph_input: no `messages` key, so checkpointed history survives.
    return await graph.ainvoke({"prompt": prompt}, config)


async def test_rewind_then_rerun_excludes_original_exchange() -> None:
    graph = _graph()
    cfg = {"configurable": {"thread_id": "t1"}}
    await _turn(graph, cfg, "first")
    await _turn(graph, cfg, "second")

    original = await rewind_last_exchange(graph, cfg)
    assert [m["content"] for m in original][-2:] == ["second", "re:second:2"]

    out = await _turn(graph, cfg, "second")
    assert [m["content"] for m in out["seen"]] == ["first", "re:first:0"]
    contents = [m["content"] for m in out["messages"]]
    assert contents == ["first", "re:first:0", "second", "re:second:2"]
    assert len(out["messages"]) == 4


async def test_restore_brings_back_original_history() -> None:
    graph = _graph()
    cfg = {"configurable": {"thread_id": "t2"}}
    await _turn(graph, cfg, "first")
    original = await rewind_last_exchange(graph, cfg)
    assert (await graph.aget_state(cfg)).values["messages"] == []

    await restore_messages(graph, cfg, original)
    assert (await graph.aget_state(cfg)).values["messages"] == original
    nxt = await _turn(graph, cfg, "again")
    assert len(nxt["seen"]) == 2


async def test_rewind_refuses_history_not_ending_in_a_pair() -> None:
    graph = _graph()
    cfg = {"configurable": {"thread_id": "t3"}}
    with pytest.raises(RetryRewindError):
        await rewind_last_exchange(graph, cfg)


async def test_rewind_does_not_touch_other_threads() -> None:
    graph = _graph()
    a = {"configurable": {"thread_id": "a"}}
    b = {"configurable": {"thread_id": "b"}}
    await _turn(graph, a, "one")
    await _turn(graph, b, "two")
    await rewind_last_exchange(graph, a)
    assert len((await graph.aget_state(b)).values["messages"]) == 2


async def test_history_rewindable_checks_the_trailing_pair():
    from unittest.mock import AsyncMock, MagicMock

    from ze_core.conversation.rewind import history_rewindable

    graph = MagicMock()
    graph.aget_state = AsyncMock(
        return_value=MagicMock(
            values={"messages": [{"role": "user"}, {"role": "assistant"}]}
        )
    )
    assert await history_rewindable(graph, {}) is True
    graph.aget_state = AsyncMock(
        return_value=MagicMock(values={"messages": [{"role": "assistant"}]})
    )
    assert await history_rewindable(graph, {}) is False
    graph.aget_state = AsyncMock(return_value=MagicMock(values={}))
    assert await history_rewindable(graph, {}) is False
