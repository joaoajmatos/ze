from __future__ import annotations

from ze_agents.claims import ClaimKind, Provenance
from ze_automation.goals.types import EligibleLearning
from ze_priority.learning_context import LearningContextAdapter


async def test_adapter_returns_only_active_eligible_context():
    from unittest.mock import AsyncMock
    from uuid import uuid4

    store = AsyncMock()
    store.list_eligible_learnings = AsyncMock(
        return_value=[
            EligibleLearning(
                id=uuid4(),
                content="short loops work",
                claim_kind=ClaimKind.INFERENCE,
                provenance=Provenance.SYNTHESIZED,
                confidence=0.4,
                evidence_summary="two traces",
                relevance=0.8,
            )
        ]
    )
    adapter = LearningContextAdapter(store)
    items = await adapter.list_context("loops")
    store.list_eligible_learnings.assert_awaited_once()
    assert len(items) == 1
    assert items[0].claim_kind is ClaimKind.INFERENCE
    assert items[0].content == "short loops work"


async def test_adapter_does_not_touch_overrides_or_push():
    from unittest.mock import AsyncMock

    store = AsyncMock()
    store.list_eligible_learnings = AsyncMock(return_value=[])
    adapter = LearningContextAdapter(store)
    await adapter.list_context()
    assert not hasattr(adapter, "create_override")
    assert store.create_override.called is False
