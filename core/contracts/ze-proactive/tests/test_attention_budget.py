from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from ze_proactive.attention_budget import (
    ATTENTION_PUSH_EVENT_KEY,
    budget_status,
    release_shared,
    try_claim_shared,
    within_budget,
)


NOW = datetime(2026, 1, 2, 12, tzinfo=timezone.utc)


def _stamps(hours_ago: list[float]) -> list[datetime]:
    return sorted(NOW - timedelta(hours=h) for h in hours_ago)


def _push_log(
    *, count: int = 0, claim_result: bool = True, hours_ago: list[float] | None = None
) -> MagicMock:
    push_log = MagicMock()
    stamps = (
        _stamps(hours_ago)
        if hours_ago is not None
        else _stamps([float(i + 1) for i in range(count)])
    )
    push_log.window_sent_at = AsyncMock(return_value=stamps)
    push_log.try_claim = AsyncMock(return_value=claim_result)
    push_log.release_claim = AsyncMock()
    return push_log


async def test_within_budget_true_when_under_max():
    push_log = _push_log(count=1)
    assert await within_budget(push_log, 3) is True
    push_log.window_sent_at.assert_awaited_once_with(ATTENTION_PUSH_EVENT_KEY, 24.0)


async def test_within_budget_false_when_at_max():
    push_log = _push_log(count=3)
    assert await within_budget(push_log, 3) is False


async def test_within_budget_permissive_on_store_failure():
    push_log = MagicMock()
    push_log.window_sent_at = AsyncMock(side_effect=RuntimeError("db down"))
    assert await within_budget(push_log, 3) is True


async def test_try_claim_shared_wins_when_under_budget_and_unclaimed():
    push_log = _push_log(count=0, claim_result=True)
    source_id = uuid4()
    claimed = await try_claim_shared(push_log, f"hypothesis:{source_id}", 3)
    assert claimed is True
    push_log.try_claim.assert_awaited_once_with(
        ATTENTION_PUSH_EVENT_KEY,
        idempotency_key=f"hypothesis:{source_id}",
        payload=None,
    )


async def test_try_claim_shared_fails_when_budget_exhausted():
    push_log = _push_log(count=3, claim_result=True)
    claimed = await try_claim_shared(push_log, f"loop:{uuid4()}", 3)
    assert claimed is False
    push_log.try_claim.assert_not_awaited()


async def test_try_claim_shared_fails_when_already_claimed():
    push_log = _push_log(count=0, claim_result=False)
    claimed = await try_claim_shared(push_log, f"loop:{uuid4()}", 3)
    assert claimed is False


async def test_try_claim_shared_passes_payload_through():
    push_log = _push_log(count=0, claim_result=True)
    await try_claim_shared(push_log, f"goal:{uuid4()}", 3, payload="rationale text")
    _, kwargs = push_log.try_claim.call_args
    assert kwargs["payload"] == "rationale text"


async def test_release_shared_releases_the_matching_key():
    push_log = _push_log()
    source_id = uuid4()
    await release_shared(push_log, f"hypothesis:{source_id}")
    push_log.release_claim.assert_awaited_once_with(
        ATTENTION_PUSH_EVENT_KEY, idempotency_key=f"hypothesis:{source_id}"
    )


async def test_shared_budget_caps_across_source_kinds():
    """A hypothesis claim and a loop claim share the same counter — the point of
    the shared budget (User Story 3)."""
    push_log = _push_log(count=3, claim_result=True)
    assert await try_claim_shared(push_log, f"hypothesis:{uuid4()}", 3) is False
    assert await try_claim_shared(push_log, f"loop:{uuid4()}", 3) is False


async def test_three_hypothesis_claims_exhaust_the_shared_budget_for_a_loop_claim():
    """Exhausts `max_pushes_per_day` via three `try_claim_shared(..., "hypothesis",
    ...)` calls against a real-ish counting push_log, then asserts a fourth
    `try_claim_shared(..., "loop", ...)` call the same day is withheld — the two
    mechanisms share one counter, not two independent ones (User Story 3)."""
    sent_count = 0

    async def window_sent_at(_event_type: str, _hours: float) -> list[datetime]:
        return _stamps([float(i + 1) for i in range(sent_count)])

    async def try_claim(
        _event_type: str, *, idempotency_key: str, payload=None
    ) -> bool:
        nonlocal sent_count
        sent_count += 1
        return True

    push_log = MagicMock()
    push_log.window_sent_at = AsyncMock(side_effect=window_sent_at)
    push_log.try_claim = AsyncMock(side_effect=try_claim)

    for _ in range(3):
        assert await try_claim_shared(push_log, f"hypothesis:{uuid4()}", 3) is True

    assert await try_claim_shared(push_log, f"loop:{uuid4()}", 3) is False


async def test_budget_status_used_and_remaining():
    status = await budget_status(_push_log(hours_ago=[5, 2]), 3)
    assert (status.used, status.remaining, status.max_per_day) == (2, 1, 3)
    assert status.next_slot_at is None


async def test_budget_status_next_slot_is_oldest_plus_window_when_full():
    status = await budget_status(_push_log(hours_ago=[20, 10, 2]), 3)
    assert status.remaining == 0
    assert status.next_slot_at == NOW - timedelta(hours=20) + timedelta(hours=24)


async def test_budget_status_next_slot_when_used_exceeds_max():
    status = await budget_status(_push_log(hours_ago=[22, 20, 10, 2]), 3)
    assert status.used == 4
    assert status.next_slot_at == NOW - timedelta(hours=20) + timedelta(hours=24)


async def test_budget_status_no_slot_when_max_zero():
    status = await budget_status(_push_log(hours_ago=[]), 0)
    assert status.remaining == 0 and status.next_slot_at is None


async def test_budget_status_raises_on_store_failure():
    push_log = MagicMock()
    push_log.window_sent_at = AsyncMock(side_effect=RuntimeError("db down"))
    with pytest.raises(RuntimeError):
        await budget_status(push_log, 3)
