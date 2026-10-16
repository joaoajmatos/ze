"""JSON form of a parked loop, so a held goal milestone survives in `held_writes.payload`."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from ze_agents.park import ParkedLoop, ParkedWrite
from ze_agents.types import ToolCall


def loop_to_dict(loop: ParkedLoop) -> dict[str, Any]:
    """A JSON-safe dict; values that are not JSON (tool results) become strings."""
    return json.loads(json.dumps(asdict(loop), default=str))


def _tool_call(data: dict[str, Any]) -> ToolCall:
    fields = dict(data)
    if fields.get("parked") is not None:
        fields["parked"] = ParkedWrite(**fields["parked"])
    if fields.get("child_loop") is not None:
        fields["child_loop"] = loop_from_dict(fields["child_loop"])
    return ToolCall(**fields)


def loop_from_dict(data: dict[str, Any]) -> ParkedLoop:
    return ParkedLoop(
        agent=data["agent"],
        messages=list(data["messages"]),
        accumulated=[_tool_call(tc) for tc in data.get("accumulated") or []],
        iteration=int(data["iteration"]),
        parked=[ParkedWrite(**pw) for pw in data.get("parked") or []],
        child=loop_from_dict(data["child"]) if data.get("child") else None,
        child_call_id=data.get("child_call_id"),
        child_arguments=data.get("child_arguments"),
    )
