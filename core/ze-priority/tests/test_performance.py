from __future__ import annotations

import time
from unittest.mock import AsyncMock

from ze_priority.view import PriorityView

from tests.factories import make_hypothesis, make_loop, make_stuck_goal


async def test_rank_completes_within_500ms_for_a_typical_working_set():
    """SC-001: tens of items per source, ranked in under 500ms."""
    loop_store = AsyncMock()
    loop_store.list.return_value = [make_loop() for _ in range(40)]
    goal_store = AsyncMock()
    goal_store.list_stuck.return_value = [make_stuck_goal() for _ in range(40)]
    hypothesis_store = AsyncMock()
    hypothesis_store.list_recent.return_value = [make_hypothesis() for _ in range(40)]

    view = PriorityView(loop_store, goal_store, hypothesis_store)

    started = time.perf_counter()
    ranking = await view.rank()
    elapsed_ms = (time.perf_counter() - started) * 1000

    assert len(ranking.items) == 120
    assert elapsed_ms < 500
