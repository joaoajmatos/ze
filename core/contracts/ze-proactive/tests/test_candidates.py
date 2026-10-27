from __future__ import annotations

from uuid import uuid4

from ze_proactive.candidates import BarThresholds, PushCandidate
from ze_proactive.types import OncePer


async def _relevance() -> float:
    return 0.7


async def _labels() -> tuple[str, ...]:
    return ("a",)


def test_thresholds_hold_the_five_conditions():
    t = BarThresholds(0.5, 0.5, 0.85, 0.3, None)
    assert t.inline_cooldown_hours is None
    assert (t.confidence, t.relevance, t.novelty_similarity_max, t.grounding) == (
        0.5,
        0.5,
        0.85,
        0.3,
    )


async def test_candidate_thunks_are_awaited_on_demand():
    c = PushCandidate(
        source_kind="test_kind",
        source_id=uuid4(),
        entity=object(),
        body="b",
        claim="c",
        confidence=0.9,
        relevance=_relevance,
        evidence_labels=_labels,
        once_per=OncePer("k"),
    )
    assert await c.relevance() == 0.7
    assert await c.evidence_labels() == ("a",)
