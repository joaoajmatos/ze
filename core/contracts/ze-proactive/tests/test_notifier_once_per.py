from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from structlog.testing import capture_logs

from ze_proactive.notifier import ProactiveNotifier
from ze_proactive.testing import InMemoryPushLog
from ze_proactive.types import NotificationRow, OncePer, PushKind, QuietHoursSetting

ACC = PushKind("oc_acc", "accountability", "normal", "tests")
DIS = PushKind("oc_dis", "discretionary", "normal", "tests")

NOON = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
NIGHT = datetime(2026, 6, 15, 2, 0, tzinfo=timezone.utc)
QUIET = QuietHoursSetting(True, time(23), time(8), "UTC", None)
KEY = OncePer("job:weekly", within=timedelta(days=6))


class Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def _row(**kw):
    d = dict(
        id="n-1",
        event_type="x",
        source="tests",
        title="T",
        body="B",
        target_type=None,
        target_id=None,
        target_parent_id=None,
        created_at=NOON,
        read_at=None,
        push_class="accountability",
        urgency="normal",
        format="text",
        actions=[],
        delivery="delivered",
        delivered_at=None,
    )
    d.update(kw)
    return NotificationRow(**d)


def _make(*, now=NOON, setting=None, cap=5, log=None):
    clock = Clock(now)
    log = log if log is not None else InMemoryPushLog(clock)
    store = AsyncMock()
    store.create = AsyncMock(side_effect=lambda **kw: _row(**kw))
    interface = AsyncMock()
    settings = None
    if setting is not None:
        settings = MagicMock()
        settings.get = AsyncMock(return_value=setting)
    n = ProactiveNotifier(
        interface,
        store,
        push_log=log,
        settings_store=settings,
        max_discretionary_per_day=cap,
        clock=clock,
    )
    return n, interface, store, log, clock


def _push_fails(interface):
    interface.push = AsyncMock(side_effect=RuntimeError("boom"))


@pytest.mark.parametrize("kind", [ACC, DIS])
@pytest.mark.parametrize(
    "scenario,first,kept",
    [
        ("push_raises", "failed", False),
        ("persist_raises", "failed", False),
        ("over_budget", "suppressed_budget", False),
        ("quiet_hours", "held", True),
        ("ok", "delivered", True),
    ],
)
async def test_only_a_sent_push_keeps_the_claim(kind, scenario, first, kept):
    if kind is ACC and scenario == "over_budget":
        pytest.skip("accountability pushes take no budget")
    n, interface, store, log, _ = _make(
        now=NIGHT if scenario == "quiet_hours" else NOON,
        setting=QUIET if scenario == "quiet_hours" else None,
        cap=0 if scenario == "over_budget" else 5,
    )
    if scenario == "push_raises":
        _push_fails(interface)
    if scenario == "persist_raises":
        store.create = AsyncMock(side_effect=RuntimeError("db"))

    assert await n.notify(kind, "t", "b", once_per=KEY) == first

    assert await n.on_cooldown(KEY) is kept
    store.create = AsyncMock(side_effect=lambda **kw: _row(**kw))
    interface.push = AsyncMock()
    second = await n.notify(kind, "t", "b", once_per=KEY)
    if kept:
        assert second == "deduped"
        store.create.assert_not_awaited()
    else:
        assert second != "deduped"


async def test_a_retry_after_a_failure_is_delivered_then_cools():
    n, interface, _, _, _ = _make()
    _push_fails(interface)
    assert await n.notify(DIS, "t", "b", once_per=KEY) == "failed"
    interface.push = AsyncMock()
    assert await n.notify(DIS, "t", "b", once_per=KEY) == "delivered"
    assert await n.notify(DIS, "t", "b", once_per=KEY) == "deduped"


async def test_the_claim_expires_with_its_window():
    n, _, _, _, clock = _make()
    assert await n.notify(DIS, "t", "b", once_per=KEY) == "delivered"
    clock.now = NOON + timedelta(days=5)
    assert await n.notify(DIS, "t", "b", once_per=KEY) == "deduped"
    clock.now = NOON + timedelta(days=7)
    assert await n.notify(DIS, "t", "b", once_per=KEY) == "delivered"


async def test_a_key_without_a_window_is_once_ever():
    n, _, _, _, clock = _make()
    assert await n.notify(DIS, "t", "b", once_per=OncePer("insight:1")) == "delivered"
    clock.now = NOON + timedelta(days=400)
    assert await n.notify(DIS, "t", "b", once_per=OncePer("insight:1")) == "deduped"


async def test_two_keys_in_one_window_both_win():
    n, _, _, _, _ = _make()
    assert await n.notify(DIS, "t", "b", once_per=OncePer("a")) == "delivered"
    assert await n.notify(DIS, "t", "b", once_per=OncePer("b")) == "delivered"


async def test_a_requested_push_takes_no_claim():
    n, _, _, log, _ = _make()
    req = PushKind("oc_req", "requested", "high", "tests")
    await n.notify(req, "t", "b")
    assert log.rows == []


async def test_a_claim_store_error_lets_the_push_through():
    log = MagicMock()
    log.claim = AsyncMock(side_effect=RuntimeError("lock timeout"))
    log.release = AsyncMock()
    n, _, _, _, _ = _make(log=log)
    with capture_logs() as logs:
        assert await n.notify(DIS, "t", "b", once_per=KEY) == "delivered"
    log.release.assert_not_awaited()
    assert any(e["event"] == "push_claim_failed" and e["key"] == KEY.key for e in logs)


async def test_deliver_held_never_claims_and_a_failed_release_keeps_the_claim():
    held = [_row(id="a", delivery="held")]
    n, interface, store, log, clock = _make(now=NIGHT, setting=QUIET)
    assert await n.notify(DIS, "t", "b", once_per=KEY) == "held"
    assert len(log.rows) == 1

    clock.now = NOON
    store.list_held = AsyncMock(return_value=held)
    store.mark_released = AsyncMock()
    store.mark_failed = AsyncMock()
    interface.push = AsyncMock(side_effect=RuntimeError("boom"))
    claimed_before = len(log.rows)
    await n.deliver_held()
    assert len(log.rows) == claimed_before
    assert await n.on_cooldown(KEY) is True


async def test_budget_counts_only_discretionary_claims():
    n, _, _, log, _ = _make(cap=1)
    assert await n.notify(ACC, "t", "b", once_per=OncePer("acc")) == "delivered"
    assert await n.notify(DIS, "t", "b", once_per=OncePer("d1")) == "delivered"
    assert (await n.budget_status()).used == 1
    assert await n.notify(DIS, "t", "b", once_per=OncePer("d2")) == "suppressed_budget"
    assert await n.recent_discretionary_bodies(24) == ["b"]
