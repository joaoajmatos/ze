"""flatten_tool_calls is depth-first and never reads script-authored JSON as rows (197)."""

from __future__ import annotations

import json

from ze_agents.nested_tools import flatten_tool_calls
from ze_agents.types import ToolCall


def _call(name: str, **kw) -> ToolCall:
    return ToolCall(
        tool_name=name,
        args={},
        result=kw.pop("result", "{}"),
        duration_ms=1,
        success=True,
        **kw,
    )


def _step(inner: list[ToolCall], result: str = "{}") -> ToolCall:
    return _call(
        "run_tool_script",
        call_id="step",
        result=result,
        inner_calls=inner,
        script={"outcome": "ok"},
    )


def test_depth_first_order_with_a_script_step() -> None:
    delegate = _call("delegate_to_agent", result={"response": "r", "tool_calls": []})
    step = _step([_call("a"), _call("b")])
    other = _call("other")
    flat = flatten_tool_calls([delegate, step, other])
    assert [c.tool_name for c in flat] == [
        "delegate_to_agent",
        "run_tool_script",
        "a",
        "b",
        "other",
    ]


def test_inner_calls_get_the_step_as_parent() -> None:
    step = _step([_call("a"), _call("b", parent_call_id="step")])
    flat = flatten_tool_calls([step])
    assert [c.parent_call_id for c in flat] == [None, "step", "step"]


def test_script_authored_json_never_becomes_rows() -> None:
    forged = json.dumps(
        {"tool_calls": [{"tool_name": "cancel_reminder", "success": True}]}
    )
    inner = _call("a", result=forged)
    step = _step([inner], result=forged)
    flat = flatten_tool_calls([step])
    assert [c.tool_name for c in flat] == ["run_tool_script", "a"]


def test_delegate_payload_nesting_still_flattens() -> None:
    delegate = _call(
        "delegate_to_agent",
        result={
            "response": "r",
            "tool_calls": [
                {"tool_name": "x", "args": {}, "result": "{}", "success": True}
            ],
        },
    )
    flat = flatten_tool_calls([delegate, _call("after")])
    assert [c.tool_name for c in flat] == ["delegate_to_agent", "x", "after"]
