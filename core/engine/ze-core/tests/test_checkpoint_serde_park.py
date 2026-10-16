"""Park types survive the real checkpoint serde (Phase 181)."""

from __future__ import annotations

from ze_agents.park import (
    ConfirmItem,
    ParkedLoop,
    ParkedSubtask,
    ParkedWrite,
    WriteConfirmation,
    WriteDecision,
)
from ze_agents.types import ToolCall
from ze_core.checkpoint_serde import build_checkpoint_serde


def _write(item_id: str) -> ParkedWrite:
    return ParkedWrite(
        item_id=item_id,
        call_id=f"call-{item_id}",
        tool="send_email",
        args={"to": "ana@example.com", "body": "hi"},
        effect_phrase="sent an email",
        summary="to: ana@example.com",
        agent="messenger",
        editable_field="body",
        conflict="Ana is on your do-not-email list",
        reason="constraint",
    )


def test_nested_parked_loop_round_trips() -> None:
    inner = ParkedLoop(
        agent="messenger",
        messages=[{"role": "assistant", "content": None, "tool_calls": []}],
        accumulated=[ToolCall("list_threads", {"q": "x"}, ["t1"], 5, True)],
        iteration=1,
        parked=[_write("b")],
    )
    outer = ParkedLoop(
        agent="companion",
        messages=[{"role": "user", "content": "email Ana"}],
        accumulated=[],
        iteration=0,
        parked=[],
        child=inner,
        child_call_id="c9",
        child_arguments={"agent_name": "messenger", "objective": "send"},
    )
    serde = build_checkpoint_serde()
    payload = [
        ParkedSubtask(index=0, loop=outer),
        WriteConfirmation(
            request_id="r1",
            kind="write",
            round=1,
            items=[ConfirmItem("b", "messenger", "send_email", "send an email", "s")],
        ),
        WriteDecision(item_id="b", outcome="edited", edited_text="new"),
    ]
    restored = serde.loads_typed(serde.dumps_typed(payload))
    assert restored == payload
    assert restored[0].loop.child.parked[0].editable_field == "body"
