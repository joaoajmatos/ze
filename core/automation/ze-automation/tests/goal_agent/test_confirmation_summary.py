"""abandon_goal's confirmation names the goal, not its id (Phase 181, e2e finding 2)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from ze_automation.agents.goals.tools import _goal_title


async def test_the_summary_is_the_goal_title() -> None:
    goal_id = uuid4()
    store = AsyncMock()
    store.get_goal = AsyncMock(return_value=SimpleNamespace(title="Write a novel"))

    assert await _goal_title({"goal_id": str(goal_id), "store": store}) == (
        '"Write a novel"'
    )
    store.get_goal.assert_awaited_once_with(goal_id)


async def test_an_unknown_goal_has_no_summary() -> None:
    store = AsyncMock()
    store.get_goal = AsyncMock(return_value=None)

    assert await _goal_title({"goal_id": str(uuid4()), "store": store}) is None
