from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from ze_priority.compose import WorldComposer
from ze_priority.errors import ZePriorityError
from ze_priority.types import PriorityRanking
from ze_priority.view import PriorityView
from ze_worldstate.types import LoopState

from tests.factories import make_held_write, make_loop

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)


def _ranking(failed=()):
    return PriorityRanking(
        items=[],
        sources_succeeded={"loop", "goal", "hypothesis"} - set(failed),
        sources_failed=set(failed),
        generated_at=NOW,
    )


def _composer(
    *,
    loops=None,
    goals=None,
    held=None,
    ranking=None,
    workflows=None,
    executions=None,
    embedder=None,
):
    view = MagicMock(spec=PriorityView)
    view.rank = AsyncMock(return_value=ranking or _ranking())
    loop_store = AsyncMock()
    loop_store.list = AsyncMock(return_value=loops if loops is not None else [])
    goal_store = AsyncMock()
    goal_store.list_progress = AsyncMock(
        return_value=goals if goals is not None else []
    )
    held_store = AsyncMock()
    held_store.list = AsyncMock(return_value=held if held is not None else [])
    wf_store = AsyncMock()
    wf_store.list_all = AsyncMock(return_value=workflows or [])
    wf_store.list_executions = AsyncMock(return_value=executions or [])
    composer = WorldComposer(
        priority_view=view,
        loop_store=loop_store,
        goal_store=goal_store,
        workflow_store=wf_store,
        held_write_store=held_store,
        embedder=embedder,
        clock=lambda: NOW,
    )
    return composer, view, loop_store, goal_store, held_store


async def test_slipping_serializes_components_with_the_shared_serializer():
    drifting = make_loop(
        title="Reply to Ana",
        state=LoopState.DRIFTING,
        drift_deadline=NOW - timedelta(days=2),
        updated_at=NOW - timedelta(days=1),
    )
    composer, *_ = _composer(loops=[drifting])

    composition = await composer.compose_slipping()

    assert composition.headline == "1 SLIPPING · 0 AT RISK"
    assert [c["type"] for c in composition.components] == [
        "headline",
        "claim_timeline",
        "claim_card",
    ]
    card = composition.components[2]
    assert card["claim"]["ref_id"] == str(drifting.id)
    assert "confidence_from" not in card["claim"]
    assert composition.sources_failed == []


async def test_loop_card_carries_confidence_from_when_the_prior_is_stored():
    drifting = make_loop(
        title="Reply to Ana",
        state=LoopState.DRIFTING,
        drift_deadline=NOW - timedelta(days=2),
        updated_at=NOW - timedelta(days=1),
        confidence_prior=0.7,
    )
    composer, *_ = _composer(loops=[drifting])

    composition = await composer.compose_slipping()

    card = composition.components[2]
    assert card["claim"]["confidence_from"] == 0.7


async def test_sources_are_read_in_parallel():
    barrier = asyncio.Barrier(3)

    async def meet(value):
        await asyncio.wait_for(barrier.wait(), timeout=1)
        return value

    composer, view, loop_store, goal_store, _ = _composer()

    async def rank():
        return await meet(_ranking())

    async def list_loops(*_):
        return await meet([])

    async def list_progress():
        return await meet([])

    view.rank = AsyncMock(side_effect=rank)
    loop_store.list = AsyncMock(side_effect=list_loops)
    goal_store.list_progress = AsyncMock(side_effect=list_progress)

    composition = await composer.compose_slipping()

    assert composition.sources_failed == []


async def test_a_failing_source_is_dropped_and_named():
    composer, _, _, goal_store, _ = _composer(loops=[make_loop(state=LoopState.ACTIVE)])
    goal_store.list_progress = AsyncMock(side_effect=RuntimeError("db down"))

    composition = await composer.compose_slipping()

    assert composition.sources_failed == ["goals"]
    assert composition.components[0]["text"] == "NOTHING SLIPPING"
    assert "goals" in composition.summary


async def test_priority_view_failed_kinds_are_reported():
    composer, *_ = _composer(ranking=_ranking(failed={"hypothesis"}))
    composition = await composer.compose_slipping()
    assert composition.sources_failed == ["hypothesis"]


async def test_priority_view_raising_counts_as_priority_failed():
    composer, view, *_ = _composer()
    view.rank = AsyncMock(side_effect=ZePriorityError("all sources failed"))
    composition = await composer.compose_slipping()
    assert composition.sources_failed == ["priority"]


async def test_every_source_failed_says_so():
    composer, view, loop_store, goal_store, _ = _composer()
    view.rank = AsyncMock(side_effect=ZePriorityError("x"))
    loop_store.list = AsyncMock(side_effect=RuntimeError("x"))
    goal_store.list_progress = AsyncMock(side_effect=RuntimeError("x"))

    composition = await composer.compose_slipping()

    assert composition.headline == "COULD NOT READ THE WORLD"
    assert [c["type"] for c in composition.components] == ["headline"]
    assert composition.summary == "I could not read any of my sources just now."


async def test_decisions_reads_open_held_writes_only():
    from ze_automation.holds.types import HeldWriteStatus

    hold = make_held_write(expires_at=NOW + timedelta(hours=3))
    composer, _, _, _, held_store = _composer(held=[hold])

    composition = await composer.compose_decisions()

    held_store.list.assert_awaited_once_with(HeldWriteStatus.OPEN)
    assert composition.headline == "1 TO DECIDE"
    assert composition.components[1]["claim"]["subject"] == "held_write"


async def test_decisions_do_not_read_the_priority_view():
    composer, view, *_ = _composer()
    await composer.compose_decisions()
    view.rank.assert_not_awaited()


class _Embedder:
    def encode_passage(self, text):
        import numpy as np

        if isinstance(text, list):
            return np.array([self.encode_passage(t) for t in text])
        return np.array(
            [1.0 if w in text.lower() else 0.0 for w in ("ledgerlite", "launch")]
        )


async def test_topic_reads_executions_only_for_matched_workflows():
    from tests.compose.test_rules_topic import _execution, _workflow

    hit = _workflow("LedgerLite launch checklist")
    miss = _workflow("Passport reminders", description="Renew documents")
    composer, *_ = _composer(
        workflows=[hit, miss],
        executions=[_execution("failed", error="timed out")],
        embedder=_Embedder(),
    )
    composer._workflow_store.list_executions = AsyncMock(
        return_value=[_execution("failed", error="timed out")]
    )

    composition = await composer.compose_topic("ledgerlite launch")

    composer._workflow_store.list_executions.assert_awaited_once_with(hit.id, limit=1)
    cards = [c for c in composition.components if c["type"] == "claim_card"]
    assert [c["title"] for c in cards] == ["LedgerLite launch checklist"]
    assert cards[0]["claim"]["state"] == "failed"
    assert composition.headline == "LEDGERLITE · 1 SLIPPED · 1 WORKFLOWS"


async def test_topic_without_an_embedder_is_empty():
    composer, *_ = _composer(embedder=None)
    composition = await composer.compose_topic("anything")
    assert composition.summary == "I can't match topics right now."


@pytest.mark.parametrize("name", ["compose_slipping", "compose_decisions"])
async def test_compose_never_raises_for_a_broken_store(name):
    composer, view, loop_store, goal_store, held_store = _composer()
    for store in (loop_store, goal_store, held_store):
        for attr in ("list", "list_progress"):
            setattr(store, attr, AsyncMock(side_effect=RuntimeError("down")))
    view.rank = AsyncMock(side_effect=RuntimeError("down"))
    composition = await getattr(composer, name)()
    assert composition.components


async def test_topic_matching_batches_encodes_and_runs_off_the_event_loop():
    import threading

    from tests.compose.test_rules_topic import _workflow

    calls: list[tuple[bool, int]] = []
    main = threading.get_ident()

    class _Spy(_Embedder):
        def encode_passage(self, text):
            if isinstance(text, list):
                calls.append((threading.get_ident() != main, len(text)))
                return super().encode_passage(text)
            return _Embedder.encode_passage(self, text)

    loops = [make_loop(title=f"LedgerLite launch {i}", state=LoopState.ACTIVE) for i in range(5)]
    composer, *_ = _composer(
        loops=loops, workflows=[_workflow(f"LedgerLite {i}") for i in range(4)], embedder=_Spy()
    )
    await composer.compose_topic("ledgerlite launch")

    assert all(off_loop for off_loop, _ in calls)
    assert len(calls) <= 8
    assert max(n for _, n in calls) >= 4
