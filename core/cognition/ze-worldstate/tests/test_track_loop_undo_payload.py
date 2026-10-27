"""Undo payload for track_loop (Phase 180): only a freshly created loop is undoable."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from ze_agents.errors import ZeError
from ze_agents.tool import get_tool
from ze_worldstate.agents.agent import LoopsAgent
from ze_worldstate.types import (
    LoopProvenance,
    LoopState,
    OpenLoop,
    TrackOutcome,
    TrackResult,
)

import ze_worldstate.agents.tools  # noqa: F401


class FakeTracker:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error

    async def track(
        self, title: str, window_days: int = 0, session_id: str | None = None
    ) -> TrackResult:
        if self.error is not None:
            raise self.error
        return self.result


def _result(outcome: TrackOutcome) -> TrackResult:
    return TrackResult(
        ok=True,
        outcome=outcome,
        loop=OpenLoop(
            id=uuid4(),
            title="Porto move",
            provenance=LoopProvenance.USER_DECLARED,
            confidence=0.9,
            state=LoopState.ACTIVE,
        ),
    )


async def _track(tracker) -> dict:
    return await get_tool("track_loop").func(loop_tracker=tracker, title="Porto move")


async def test_created_returns_undo_payload():
    result = _result(TrackOutcome.CREATED)
    out = await _track(FakeTracker(result))
    assert out["undo"] == {"loop_id": str(result.loop.id)}


@pytest.mark.parametrize(
    "outcome",
    [TrackOutcome.CONFIRMED, TrackOutcome.REINFORCED, TrackOutcome.REVIVED],
)
async def test_existing_loop_outcomes_have_no_payload(outcome):
    out = await _track(FakeTracker(_result(outcome)))
    assert out["ok"] is True
    assert "undo" not in out


async def test_failed_result_has_no_payload():
    out = await _track(FakeTracker(TrackResult(ok=False, error="db down")))
    assert "undo" not in out


async def test_ze_error_has_no_payload():
    out = await _track(FakeTracker(error=ZeError("boom")))
    assert "undo" not in out


def test_tool_deps_has_the_keys_the_loop_used():
    store, tracker, lifecycle = MagicMock(), MagicMock(), MagicMock()
    agent = LoopsAgent(
        openrouter_client=AsyncMock(),
        loop_store=store,
        loop_tracker=tracker,
        lifecycle=lifecycle,
    )
    assert agent.tool_deps() == {
        "loop_store": store,
        "loop_tracker": tracker,
        "lifecycle": lifecycle,
    }
