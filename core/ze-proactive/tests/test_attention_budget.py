from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from ze_proactive.attention_budget import (
    ATTENTION_PUSH_EVENT_KEY,
    release_shared,
    try_claim_shared,
    within_budget,
)


def _push_log(*, count: int = 0, claim_result: bool = True) -> MagicMock:
    push_log = MagicMock()
    push_log.count_sent_within_hours = AsyncMock(return_value=count)
    push_log.try_claim = AsyncMock(return_value=claim_result)
    push_log.release_claim = AsyncMock()
    return push_log


async def test_within_budget_true_when_under_max():
    push_log = _push_log(count=1)
    assert await within_budget(push_log, 3) is True
    push_log.count_sent_within_hours.assert_awaited_once_with(
        ATTENTION_PUSH_EVENT_KEY, 24.0
    )


async def test_within_budget_false_when_at_max():
    push_log = _push_log(count=3)
    assert await within_budget(push_log, 3) is False


async def test_within_budget_permissive_on_store_failure():
    push_log = MagicMock()
    push_log.count_sent_within_hours = AsyncMock(side_effect=RuntimeError("db down"))
    assert await within_budget(push_log, 3) is True


async def test_try_claim_shared_wins_when_under_budget_and_unclaimed():
    push_log = _push_log(count=0, claim_result=True)
    source_id = uuid4()
    claimed = await try_claim_shared(push_log, "hypothesis", source_id, 3)
    assert claimed is True
    push_log.try_claim.assert_awaited_once_with(
        ATTENTION_PUSH_EVENT_KEY,
        idempotency_key=f"hypothesis:{source_id}",
        payload=None,
    )


async def test_try_claim_shared_fails_when_budget_exhausted():
    push_log = _push_log(count=3, claim_result=True)
    claimed = await try_claim_shared(push_log, "loop", uuid4(), 3)
    assert claimed is False
    push_log.try_claim.assert_not_awaited()


async def test_try_claim_shared_fails_when_already_claimed():
    push_log = _push_log(count=0, claim_result=False)
    claimed = await try_claim_shared(push_log, "loop", uuid4(), 3)
    assert claimed is False


async def test_try_claim_shared_passes_payload_through():
    push_log = _push_log(count=0, claim_result=True)
    await try_claim_shared(push_log, "goal", uuid4(), 3, payload="rationale text")
    _, kwargs = push_log.try_claim.call_args
    assert kwargs["payload"] == "rationale text"


async def test_release_shared_releases_the_matching_key():
    push_log = _push_log()
    source_id = uuid4()
    await release_shared(push_log, "hypothesis", source_id)
    push_log.release_claim.assert_awaited_once_with(
        ATTENTION_PUSH_EVENT_KEY, idempotency_key=f"hypothesis:{source_id}"
    )


async def test_shared_budget_caps_across_source_kinds():
    """A hypothesis claim and a loop claim share the same counter — the point of
    the shared budget (User Story 3)."""
    push_log = _push_log(count=3, claim_result=True)
    assert await try_claim_shared(push_log, "hypothesis", uuid4(), 3) is False
    assert await try_claim_shared(push_log, "loop", uuid4(), 3) is False
