from ze_core.conversation.turn import TurnResult, make_graph_input
from ze_core.orchestration import nodes
from ze_core.orchestration.graph import graph_builder
from ze_core.orchestration.state import AgentState
from ze_agents.interface.types import RawInput


def test_plan_sequential_not_exported():
    assert "plan_sequential" not in nodes.__all__
    assert not hasattr(nodes, "plan_sequential")


def test_graph_builder_has_no_plan_sequential_node():
    builder = graph_builder()
    assert "plan_sequential" not in builder.nodes


def test_agent_state_has_no_dynamic_plan_fields():
    keys = AgentState.__annotations__
    assert "dynamic_plan_steps" not in keys
    assert "dynamic_plan_high_risk" not in keys
    assert "conductor_hint" in keys
    assert "conductor_ledger" in keys


def test_make_graph_input_has_conductor_not_dynamic_plan():
    graph_input = make_graph_input(RawInput(text="hi"), "s1")
    assert "dynamic_plan_steps" not in graph_input
    assert "dynamic_plan_high_risk" not in graph_input
    assert graph_input["conductor_hint"] is None
    assert graph_input["conductor_ledger"] == []


def test_turn_result_has_no_dynamic_plan_fields():
    assert "dynamic_plan_steps" not in TurnResult.__dataclass_fields__
    assert "dynamic_plan_high_risk" not in TurnResult.__dataclass_fields__
