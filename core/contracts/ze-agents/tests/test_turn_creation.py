import json

import pytest

from ze_agents.nested_tools import TurnCreation, turn_creation
from ze_agents.types import ToolCall


def _call(name, result, *, success=True):
    return ToolCall(
        tool_name=name, args={}, result=result, duration_ms=1, success=success
    )


def test_reminder_success():
    out = turn_creation([_call("set_reminder", {"id": "r1", "label": "x"})])
    assert out == TurnCreation(reminder_id="r1", goal_id=None)


def test_goal_success_with_json_string_result():
    out = turn_creation([_call("create_goal", json.dumps({"id": "g1"}))])
    assert out == TurnCreation(reminder_id=None, goal_id="g1")


def test_both_created():
    out = turn_creation(
        [_call("set_reminder", {"id": "r1"}), _call("create_goal", {"id": "g1"})]
    )
    assert (out.reminder_id, out.goal_id) == ("r1", "g1")


@pytest.mark.parametrize(
    "call",
    [
        _call("set_reminder", {"error": "bad time"}),
        _call("set_reminder", {"id": "r1", "error": "x"}),
        _call("set_reminder", {"id": "r1"}, success=False),
        _call("set_reminder", {"label": "no id"}),
        _call("set_reminder", "not json"),
        _call("set_reminder", None),
        _call("other_tool", {"id": "r1"}),
    ],
)
def test_not_a_creation(call):
    assert turn_creation([call]) == TurnCreation()


def test_nested_call_counts():
    inner = {"tool_name": "set_reminder", "result": {"id": "r9"}, "success": True}
    outer = _call("delegate_to_agent", {"tool_calls": [inner]})
    assert turn_creation([outer]).reminder_id == "r9"


def test_nested_unsuccessful_does_not_count():
    inner = {"tool_name": "create_goal", "result": {"id": "g9"}, "success": False}
    assert (
        turn_creation([_call("delegate_to_agent", {"tool_calls": [inner]})]).goal_id
        is None
    )
