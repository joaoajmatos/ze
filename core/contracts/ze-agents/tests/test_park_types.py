"""Park types (Phase 181)."""

from __future__ import annotations

from ze_agents.errors import LoopParked, ZeError
from ze_agents.park import (
    SUMMARY_MAX_CHARS,
    ParkedLoop,
    ParkedWrite,
    generic_summary,
)
from ze_agents.types import ToolCall


def _write(item_id: str, tool: str = "delete_event") -> ParkedWrite:
    return ParkedWrite(
        item_id=item_id,
        call_id=f"call-{item_id}",
        tool=tool,
        args={"event_id": "e1"},
        effect_phrase="deleted a calendar event",
        summary="event_id: e1",
        agent="calendar",
    )


def _loop(agent: str, parked: list[ParkedWrite], child: ParkedLoop | None = None):
    return ParkedLoop(
        agent=agent,
        messages=[{"role": "user", "content": "x"}],
        accumulated=[ToolCall("list_events", {}, "r", 1, True)],
        iteration=0,
        parked=parked,
        child=child,
        child_call_id="c0" if child else None,
        child_arguments={"agent_name": child.agent} if child else None,
    )


def test_all_parked_collects_children_in_order() -> None:
    inner = _loop("calendar", [_write("b")])
    outer = _loop("companion", [_write("a", "send_email")], child=inner)
    assert [w.item_id for w in outer.all_parked()] == ["a", "b"]


def test_loop_parked_is_a_ze_error() -> None:
    loop = _loop("calendar", [_write("a")])
    exc = LoopParked(loop)
    assert isinstance(exc, ZeError)
    assert exc.loop is loop


def test_generic_summary_drops_empty_and_truncates() -> None:
    assert generic_summary({"to": "ana", "cc": None, "body": ""}) == "to: ana"
    long = generic_summary({"body": "x" * 500})
    assert len(long) <= SUMMARY_MAX_CHARS
    assert long.endswith("…")
