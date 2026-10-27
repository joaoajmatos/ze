"""Phase 170 acceptance runs (SC-001, SC-002) against a real Postgres."""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from ze_automation.goals.postgres import PostgresGoalStore
from ze_correlation.store import PostgresHypothesisStore
from ze_priority.store import PostgresPriorityOverrideStore
from ze_priority.view import PriorityView
from ze_worldstate.bootstrap import LoopPushSettings
from ze_worldstate.extraction import _create_declared_loop
from ze_worldstate.jobs.drift_sweep import DriftSweepJob
from ze_worldstate.lifecycle import LoopLifecycle
from ze_worldstate.store import PostgresLoopStore
from ze_worldstate.surfacing import LoopSurfacer
from ze_worldstate.types import LoopState

from ze_api.api.deps import require_api_key
from ze_api.api.v0.priority.router import router
from tests.pg._builders import make_goal_with_gates, utcnow

pytestmark = pytest.mark.pg


def _view(pool) -> PriorityView:
    return PriorityView(
        PostgresLoopStore(pool), PostgresGoalStore(pool), PostgresHypothesisStore(pool)
    )


async def test_declared_loop_drifts_and_is_a_push_candidate(pg_pool):
    """SC-001."""
    store = PostgresLoopStore(pg_pool)
    created = await _create_declared_loop(
        "Renew the passport", "user_declared", [], [], store, None, None, None,
        implied_window_days=1,
    )
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE open_loops SET drift_deadline = now() - interval '1 hour' WHERE id = $1",
            created.id,
        )

    await DriftSweepJob(store, LoopLifecycle(pg_pool)).run()

    drifted = await store.get(created.id)
    assert drifted.state is LoopState.DRIFTING

    ranking = await _view(pg_pool).rank()
    [item] = [i for i in ranking.items if i.source_kind == "loop"]
    assert item.priority.value > drifted.confidence

    relevance = MagicMock()
    relevance.build = AsyncMock(return_value=object())
    relevance.score = MagicMock(return_value=SimpleNamespace(value=1.0, contributions=[]))
    surfacer = LoopSurfacer(
        loop_store=store,
        graph_store=MagicMock(),
        pool=pg_pool,
        relevance_model=relevance,
        notifier=MagicMock(),
        settings=LoopPushSettings(),
    )

    candidates = await surfacer.candidates()

    assert [c.source_id for c in candidates] == [created.id]


async def test_multi_gate_goal_is_ranked_and_served_by_the_route(pg_pool):
    """SC-002."""
    now = utcnow()
    goal_id = await make_goal_with_gates(
        pg_pool,
        title="Launch the portfolio",
        status="awaiting_gate",
        gates=[
            ("approved", now - timedelta(days=40), True),
            ("awaiting_approval", now - timedelta(days=10), False),
            ("pending", None, False),
            ("pending", None, False),
            ("pending", None, False),
        ],
    )
    view = _view(pg_pool)

    ranking = await view.rank()
    assert ranking.sources_failed == set()
    assert [i.source_id for i in ranking.items if i.source_kind == "goal"] == [goal_id]

    app = FastAPI()
    app.state.container = SimpleNamespace(
        priority_view=view,
        priority_override_store=PostgresPriorityOverrideStore(pg_pool),
        collision_store=AsyncMock(),
        nli_client=AsyncMock(),
    )
    app.dependency_overrides[require_api_key] = lambda: None
    app.include_router(router, prefix="/api/v0")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.get("/api/v0/priority/snapshot")

    assert response.status_code == 200
    body = response.json()
    assert body["sources_failed"] == []
    assert "Launch the portfolio" in [i["title"] for i in body["items"]]
