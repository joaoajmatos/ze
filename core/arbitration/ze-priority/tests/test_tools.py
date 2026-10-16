from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import numpy as np
from ze_agents.claims import ClaimKind, Confidence, DecayProfile

from ze_priority.errors import StalePriorityRestoreError
from ze_priority.tools import reprioritize_item, restore_priority_override
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

    def encode_passage(self, text: str) -> np.ndarray:
        lowered = text.lower()
        return np.array([1.0 if word in lowered else 0.0 for word in self._vocab])

    encode_query = encode_passage


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
    override_store.create.side_effect = lambda o: (o, None)
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
    assert result["undo"] == {
        "override_id": result["undo"]["override_id"],
        "prior_override_id": None,
    }
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


async def test_reprioritize_item_undo_carries_prior_override_id():
    berlin = _item("the berlin move", rank=1)
    other = _item("quarterly report", rank=2)
    view = _view([berlin, other])
    prior = uuid4()
    override_store = AsyncMock()
    override_store.create.side_effect = lambda o: (o, prior)
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

    assert result["undo"]["prior_override_id"] == str(prior)
    created = override_store.create.await_args.args[0]
    assert result["undo"]["override_id"] == str(created.id)


async def test_reprioritize_item_no_undo_when_nothing_written():
    view = _view([_item("the berlin move", rank=1)])
    override_store = AsyncMock()
    embedder = _FakeEmbedder(["berlin", "move"])

    result = await reprioritize_item(
        priority_view=view,
        override_store=override_store,
        collision_store=None,
        nli_client=None,
        embedder=embedder,
        item_description="the berlin move",
        requested_relation="more_urgent",
    )

    assert result["status"] == "no_op"
    assert "undo" not in result


async def test_restore_priority_override_calls_store():
    override_store = AsyncMock()
    oid, prior = uuid4(), uuid4()

    result = await restore_priority_override(
        override_store=override_store,
        override_id=str(oid),
        prior_override_id=str(prior),
    )

    override_store.restore.assert_awaited_once_with(oid, prior)
    assert result["ok"] is True
    assert result["restored_prior"] is True


async def test_restore_priority_override_reports_prior_not_reinstated():
    override_store = AsyncMock()
    override_store.restore.return_value = None

    result = await restore_priority_override(
        override_store=override_store,
        override_id=str(uuid4()),
        prior_override_id=str(uuid4()),
    )

    assert result["ok"] is True
    assert result["restored_prior"] is False


async def test_restore_priority_override_without_prior():
    override_store = AsyncMock()
    oid = uuid4()

    result = await restore_priority_override(
        override_store=override_store, override_id=str(oid)
    )

    override_store.restore.assert_awaited_once_with(oid, None)
    assert result["ok"] is True


async def test_restore_priority_override_stale_returns_error():
    override_store = AsyncMock()
    override_store.restore.side_effect = StalePriorityRestoreError("changed")

    result = await restore_priority_override(
        override_store=override_store, override_id=str(uuid4())
    )

    assert "error" in result
    assert "ok" not in result


async def test_restore_priority_override_bad_uuid_returns_error():
    override_store = AsyncMock()

    result = await restore_priority_override(
        override_store=override_store, override_id="nope"
    )

    assert "error" in result
    override_store.restore.assert_not_called()


def test_reprioritize_item_is_reversible_with_registered_undo():
    from ze_agents.reversibility import ToolReversibility
    from ze_agents.tool import get_tool

    spec = get_tool("reprioritize_item")
    assert spec.reversibility == ToolReversibility.REVERSIBLE
    assert spec.undo_tool == "restore_priority_override"
    assert spec.undo_note == "Restores the priority order from before this change"


def test_priority_agent_declares_undo_tool_and_deps():
    from ze_priority.agent import PriorityAgent

    assert "restore_priority_override" in PriorityAgent.tools
    agent = PriorityAgent.__new__(PriorityAgent)
    agent._priority_view = "v"
    agent._override_store = "s"
    agent._collision_store = "c"
    agent._nli_client = "n"
    agent._embedder = "e"
    assert agent.tool_deps()["override_store"] == "s"
