"""B15 (phase 198): a turn registers an AbortToken so the cancel command can stop it."""

from __future__ import annotations

import asyncio
from functools import partial
from types import SimpleNamespace
from typing import Any

import langgraph.types as lg_types
from langgraph.checkpoint.memory import MemorySaver
from langgraph.constants import END
from langgraph.graph import StateGraph
from typing_extensions import TypedDict

from ze_agents.interface.types import RawInput
from ze_agents.park import ConfirmItem, WriteConfirmation
from ze_agents.types import AbortToken
from ze_core.container import Container
from ze_core.conversation.turn import invoke_raw_turn, resume_turn


class State(TypedDict, total=False):
    prompt: str
    session_id: str
    final_response: str | None
    error: str | None


class Probe:
    """Holds the graph open and records the abort token each run of `work` saw."""

    def __init__(self, *, pause: bool = False) -> None:
        self.pause = pause
        self.tokens: list[AbortToken | None] = []
        self.by_thread: dict[str, AbortToken | None] = {}
        self.started: dict[str, asyncio.Event] = {}
        self.release = asyncio.Event()

    def started_for(self, thread_id: str) -> asyncio.Event:
        return self.started.setdefault(thread_id, asyncio.Event())

    def graph(self):
        async def ask(state, config):
            if self.pause:
                lg_types.interrupt(
                    WriteConfirmation(
                        request_id="r1",
                        kind="write",
                        round=1,
                        items=[
                            ConfirmItem(
                                item_id="i1",
                                agent="calendar",
                                tool="delete_event",
                                effect_phrase="deleted an event",
                                summary="3pm",
                            )
                        ],
                    )
                )
            return {}

        async def work(state, config):
            configurable = config["configurable"]
            self.tokens.append(configurable.get("abort_token"))
            self.by_thread[configurable["thread_id"]] = configurable.get("abort_token")
            self.started_for(configurable["thread_id"]).set()
            await self.release.wait()
            return {"final_response": "Done."}

        builder = StateGraph(State)
        builder.add_node("ask", ask)
        builder.add_node("work", work)
        builder.set_entry_point("ask")
        builder.add_edge("ask", "work")
        builder.add_edge("work", END)
        return builder.compile(checkpointer=MemorySaver())


def _container(graph, *, with_registry: bool = True) -> Any:
    container = SimpleNamespace(graph=graph, interface=None)
    container._build_config = lambda thread_id, **extra: {
        "configurable": {"thread_id": thread_id, **extra}
    }
    if with_registry:
        container._abort_tokens = {}
        container.abort_invocation = partial(Container.abort_invocation, container)
    return container


async def _start(container, thread_id: str) -> asyncio.Task:
    return asyncio.create_task(
        invoke_raw_turn(container, thread_id, RawInput(text="hi"))
    )


async def test_cancel_during_a_turn_sets_the_token_the_graph_received():
    probe = Probe()
    container = _container(probe.graph())
    task = await _start(container, "t1")
    await probe.started_for("t1").wait()

    await container.abort_invocation("t1", "user cancelled")
    probe.release.set()
    await task

    assert probe.tokens[0] is not None
    assert probe.tokens[0].is_set
    assert probe.tokens[0].reason == "user cancelled"


async def test_cancel_during_a_resumed_turn_sets_the_token_the_graph_received():
    probe = Probe(pause=True)
    container = _container(probe.graph())
    first = await invoke_raw_turn(container, "t1", RawInput(text="hi"))
    assert first.interrupted

    task = asyncio.create_task(
        resume_turn(container, first.config, {"choice": "approve"}, request_id="r1")
    )
    await probe.started_for("t1").wait()
    await container.abort_invocation("t1")
    probe.release.set()
    await task

    assert probe.tokens[-1] is not None
    assert probe.tokens[-1].is_set


async def test_a_finished_turn_leaves_no_token_behind():
    probe = Probe()
    container = _container(probe.graph())
    probe.release.set()

    await invoke_raw_turn(container, "t1", RawInput(text="hi"))

    assert "t1" not in container._abort_tokens


async def test_a_paused_turn_and_its_resume_leave_no_token_behind():
    probe = Probe(pause=True)
    container = _container(probe.graph())
    probe.release.set()

    first = await invoke_raw_turn(container, "t1", RawInput(text="hi"))
    assert first.interrupted
    assert "t1" not in container._abort_tokens

    await resume_turn(container, first.config, {"choice": "approve"}, request_id="r1")
    assert "t1" not in container._abort_tokens


async def test_cancelling_one_thread_leaves_the_other_running():
    probe = Probe()
    container = _container(probe.graph())
    first = await _start(container, "t1")
    second = await _start(container, "t2")
    await probe.started_for("t1").wait()
    await probe.started_for("t2").wait()

    await container.abort_invocation("t1")
    probe.release.set()
    await asyncio.gather(first, second)

    assert probe.by_thread["t1"] is not None
    assert probe.by_thread["t1"].is_set
    assert probe.by_thread["t2"] is not None
    assert not probe.by_thread["t2"].is_set


async def test_a_finishing_turn_does_not_remove_a_newer_token():
    probe = Probe()
    container = _container(probe.graph())
    task = await _start(container, "t1")
    await probe.started_for("t1").wait()
    newer = AbortToken()
    container._abort_tokens["t1"] = newer

    probe.release.set()
    await task

    assert container._abort_tokens["t1"] is newer


async def test_a_container_without_the_registry_still_runs_the_turn():
    probe = Probe()
    container = _container(probe.graph(), with_registry=False)
    probe.release.set()

    outcome = await invoke_raw_turn(container, "t1", RawInput(text="hi"))

    assert outcome.response == "Done."
