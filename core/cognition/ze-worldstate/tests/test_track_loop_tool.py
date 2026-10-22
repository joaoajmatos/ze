from __future__ import annotations

from uuid import uuid4

from ze_agents.errors import ZeError
from ze_agents.reversibility import ToolReversibility
from ze_agents.tool import ToolAccess, get_tool, validate_tool_declarations
from ze_worldstate.types import (
    LoopProvenance,
    LoopState,
    OpenLoop,
    TrackOutcome,
    TrackResult,
)

import ze_worldstate.agents.tools  # noqa: F401  (registers the tools at import time)


class FakeTracker:
    def __init__(self, result: TrackResult | None = None, error: Exception | None = None):
        self.result = result
        self.error = error

    async def track(self, title: str, window_days: int = 0) -> TrackResult:
        if self.error is not None:
            raise self.error
        return self.result


def _ok_result() -> TrackResult:
    return TrackResult(
        ok=True,
        outcome=TrackOutcome.CREATED,
        loop=OpenLoop(
            id=uuid4(),
            title="Porto move",
            provenance=LoopProvenance.USER_DECLARED,
            confidence=0.9,
            state=LoopState.ACTIVE,
        ),
    )


def test_track_loop_declaration():
    spec = get_tool("track_loop")

    assert spec.access is ToolAccess.WRITE
    assert spec.reversibility is ToolReversibility.REVERSIBLE
    assert spec.undo_tool == "drop_loop"
    assert spec.undo_note
    assert spec.effect_phrase == "started tracking an open loop"
    validate_tool_declarations()


def test_llm_schema_lists_only_primitive_args():
    params = get_tool("track_loop").llm_schema()["function"]["parameters"]

    assert params["required"] == ["title"]
    assert params["properties"]["title"]["type"] == "string"
    assert params["properties"]["window_days"]["type"] == "integer"
    assert "loop_tracker" not in params["properties"]


async def test_tool_returns_ok_payload():
    out = await get_tool("track_loop").func(
        loop_tracker=FakeTracker(_ok_result()), title="Porto move"
    )

    assert out["ok"] is True
    assert out["outcome"] == "created"
    assert out["title"] == "Porto move"
    assert out["state"] == "active"
    assert out["id"]


async def test_tool_returns_error_payload_on_failed_result():
    out = await get_tool("track_loop").func(
        loop_tracker=FakeTracker(TrackResult(ok=False, error="db down")),
        title="Porto move",
    )

    assert out == {"ok": False, "error": "db down"}


async def test_tool_catches_ze_error():
    out = await get_tool("track_loop").func(
        loop_tracker=FakeTracker(error=ZeError("boom")), title="Porto move"
    )

    assert out["ok"] is False
    assert out["error"]
