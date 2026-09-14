from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import numpy as np
from ze_agents.claims import ClaimKind, Confidence, DecayProfile

from ze_priority.tools import reprioritize_item
from ze_priority.types import PriorityItem, PriorityRanking

UTC = timezone.utc


def _item(title: str, rank: int) -> PriorityItem:
    return PriorityItem(
        source_kind="loop",
        claim_kind=ClaimKind.PRIORITY,
        source_id=uuid4(),
        title=title,
        signal=None,
        priority=Confidence(
            value=1.0 - rank * 0.1, decay_profile=DecayProfile.TIME_LINEAR
        ),
        rank=rank,
        activity_at=datetime.now(UTC),
    )


class _FakeEmbedder:
    """Deterministic bag-of-words embedder — exact substring overlap scores high,
    unrelated text scores low. Good enough to exercise disambiguation branching
    without a real model."""

    def __init__(self, vocab: list[str]) -> None:
        self._vocab = vocab

    def encode(self, text: str) -> np.ndarray:
        lowered = text.lower()
        return np.array([1.0 if word in lowered else 0.0 for word in self._vocab])


def _view(items: list[PriorityItem]) -> AsyncMock:
    view = AsyncMock()
    view.rank.return_value = PriorityRanking(
        items=items,
        sources_succeeded={"loop", "goal", "hypothesis"},
        sources_failed=set(),
        generated_at=datetime.now(UTC),
    )
    return view


async def test_exact_match_proceeds_and_submits():
    berlin = _item("the berlin move", rank=1)
    other = _item("quarterly report", rank=2)
    view = _view([berlin, other])
    override_store = AsyncMock()
    override_store.create.side_effect = lambda o: o
    embedder = _FakeEmbedder(["berlin", "move", "quarterly", "report"])

    result = await reprioritize_item(
        priority_view=view,
        override_store=override_store,
        collision_store=None,
        nli_client=None,
        embedder=embedder,
        item_description="the berlin move",
        requested_relation="less_urgent",
    )

    assert result["status"] == "ok"
    override_store.create.assert_awaited_once()


async def test_zero_matches_returns_clarification_without_submitting():
    berlin = _item("the berlin move", rank=1)
    other = _item("quarterly report", rank=2)
    view = _view([berlin, other])
    override_store = AsyncMock()
    embedder = _FakeEmbedder(["berlin", "move", "quarterly", "report"])

    result = await reprioritize_item(
        priority_view=view,
        override_store=override_store,
        collision_store=None,
        nli_client=None,
        embedder=embedder,
        item_description="something totally unrelated",
        requested_relation="less_urgent",
    )

    assert result["status"] == "clarification_needed"
    override_store.create.assert_not_called()


async def test_ambiguous_close_scores_returns_clarification_without_submitting():
    a = _item("berlin project", rank=1)
    b = _item("berlin trip", rank=2)
    view = _view([a, b])
    override_store = AsyncMock()
    embedder = _FakeEmbedder(["berlin", "project", "trip"])

    result = await reprioritize_item(
        priority_view=view,
        override_store=override_store,
        collision_store=None,
        nli_client=None,
        embedder=embedder,
        item_description="berlin",
        requested_relation="less_urgent",
    )

    assert result["status"] == "clarification_needed"
    override_store.create.assert_not_called()
