from typing import Annotated, TypedDict

import pytest

from ze_agents.interface.types import RawInput, VoiceInput
from ze_agents.lifetime import Input, Thread, Turn, field_lifetimes, turn_reset
from ze_agents.registry import clear_registry
from ze_agents.tool import clear_tool_registry
from ze_core.conversation.turn import make_graph_input
from ze_core.orchestration.state import AgentState
from ze_core.routing.types import SubTask

from tests.orchestration import write_confirmation_harness as h


def test_voice_turn_sets_modality_and_voice_input():
    graph_input = make_graph_input(
        RawInput(text="hello", voice=VoiceInput(duration_s=3.5, edited=True)), "s"
    )
    assert graph_input["input_modality"] == "voice"
    assert graph_input["voice_input"] == {"duration_s": 3.5, "edited": True}
    assert graph_input["prompt"] == "hello"


def test_text_turn_has_no_voice_input_and_key_resets():
    graph_input = make_graph_input(RawInput(text="hello"), "s")
    assert graph_input["input_modality"] == "text"
    assert "voice_input" in graph_input
    assert graph_input["voice_input"] is None


def test_every_turn_key_equals_its_reset_and_no_thread_key_is_present():
    graph_input = make_graph_input(RawInput(text="hello"), "s")
    lifetimes = field_lifetimes(AgentState)
    reset = turn_reset(AgentState)
    for name, marker in lifetimes.items():
        if isinstance(marker, Turn):
            assert graph_input[name] == reset[name]
        elif isinstance(marker, Input):
            assert name in graph_input
        else:
            assert isinstance(marker, Thread)
            assert name not in graph_input


def test_the_input_keys_come_from_the_raw_input():
    graph_input = make_graph_input(
        RawInput(text="look", image=b"png", image_mime="image/png"), "s9"
    )
    assert graph_input["prompt"] == "look"
    assert graph_input["session_id"] == "s9"
    assert graph_input["input_modality"] == "image"
    assert graph_input["image_data"] == b"png"
    assert graph_input["image_mime"] == "image/png"


class _Extra(TypedDict):
    plugin_turn: Annotated[list, Turn(factory=list)]


class _ExtendedState(AgentState, _Extra):
    pass


def test_a_state_type_with_an_extra_turn_key_gets_it_reset():
    graph_input = make_graph_input(
        RawInput(text="hello"), "s", state_type=_ExtendedState
    )
    assert graph_input["plugin_turn"] == []
    assert graph_input["judgments"] == []


def test_the_default_state_type_has_no_plugin_keys():
    assert "plugin_turn" not in make_graph_input(RawInput(text="hello"), "s")


@pytest.fixture
def clean_registries():
    clear_registry()
    clear_tool_registry()
    h.register_tools()
    yield
    clear_registry()
    clear_tool_registry()


async def test_turn_one_state_does_not_leak_into_turn_two(clean_registries):
    seen: list[dict] = []

    async def preprocess(state, config=None):
        seen.append(
            {
                key: state.get(key)
                for key in (
                    "loop_offer_ids",
                    "open_items_query",
                    "resume_recap_applied",
                    "pre_approved_writes",
                    "messages",
                    "last_active_at",
                )
            }
        )
        return {}

    async def write_memory(state, config=None):
        if state["prompt"] != "one":
            return {}
        return {
            "loop_offer_ids": ["loop-1"],
            "open_items_query": True,
            "resume_recap_applied": True,
            "pre_approved_writes": ["send_email"],
            "messages": [{"role": "user", "content": "one"}],
            "last_active_at": 1234.0,
        }

    h.register_agent(
        "calendar", h.scripted_client(("first", None), ("second", None)), []
    )
    graph = h.compiled_graph(
        [SubTask("calendar", "do it")],
        overrides={"preprocess": preprocess, "write_memory": write_memory},
    )
    cfg = h.thread_config()
    await graph.ainvoke(h.graph_input("one"), cfg)
    await graph.ainvoke(h.graph_input("two"), cfg)

    turn_two = seen[1]
    assert turn_two["loop_offer_ids"] == []
    assert turn_two["open_items_query"] is False
    assert turn_two["resume_recap_applied"] is False
    assert turn_two["pre_approved_writes"] == []
    assert turn_two["messages"] == [{"role": "user", "content": "one"}]
    assert turn_two["last_active_at"] == 1234.0
