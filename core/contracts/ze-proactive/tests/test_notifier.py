from __future__ import annotations

from datetime import datetime, time, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from ze_agents.interface.types import Action
from ze_proactive.attention_budget import ATTENTION_PUSH_EVENT_KEY
from ze_proactive.errors import PushPolicyError
from ze_proactive.notifier import ProactiveNotifier
from ze_proactive.push_kinds import QUIET_HOURS_SUMMARY
from ze_proactive.types import NotificationRow, PushKind, QuietHoursSetting

REQ = PushKind("n_req", "requested", "high", "tests")
ACC = PushKind("n_acc", "accountability", "normal", "tests")
DIS = PushKind("n_dis", "discretionary", "normal", "tests")

NOON = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
NIGHT = datetime(2026, 6, 15, 2, 0, tzinfo=timezone.utc)
QUIET = QuietHoursSetting(True, time(23), time(8), "UTC", None)


def _row(**kw):
    d = dict(
        id="n-1",
        event_type="x",
        source="tests",
        title="T",
        body="B",
        target_type=None,
        target_id=None,
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


def _store(held=None):
    store = AsyncMock()
    store.exists_recent = AsyncMock(return_value=False)
    store.create = AsyncMock(side_effect=lambda **kw: _row(**kw))
    store.list_held = AsyncMock(return_value=held or [])
    return store


def _push_log(count=0, claim=True):
    pl = MagicMock()
    pl.count_sent_within_hours = AsyncMock(return_value=count)
    pl.try_claim = AsyncMock(return_value=claim)
    pl.release_claim = AsyncMock()
    return pl


def _settings(setting=None, error=None):
    s = MagicMock()
    s.get = AsyncMock(return_value=setting, side_effect=error)
    return s


def _make(*, store=None, push_log=None, setting=None, error=None, now=NOON, cap=5):
    interface = AsyncMock()
    store = store or _store()
    notifier = ProactiveNotifier(
        interface,
        store,
        push_log=push_log,
        settings_store=_settings(setting, error) if (setting or error) else None,
        max_discretionary_per_day=cap,
        clock=lambda: now,
    )
    return notifier, interface, store


async def test_requested_delivers_even_in_quiet_hours():
    n, iface, store = _make(setting=QUIET, now=NIGHT)
    assert await n.notify(REQ, "t", "b") == "delivered"
    sent = iface.push.call_args.args[0]
    assert sent.buzz is True and sent.urgency == "high"
    assert store.create.call_args.kwargs["delivery"] == "delivered"


async def test_accountability_delivers_outside_quiet():
    n, iface, _ = _make(setting=QUIET)
    assert await n.notify(ACC, "t", "b") == "delivered"
    assert iface.push.call_args.args[0].buzz is True


async def test_accountability_held_in_quiet_hours_sends_silent_frame():
    n, iface, store = _make(setting=QUIET, now=NIGHT)
    assert await n.notify(ACC, "t", "b") == "held"
    assert store.create.call_args.kwargs["delivery"] == "held"
    sent = iface.push.call_args.args[0]
    assert sent.delivery == "held" and sent.buzz is False


async def test_discretionary_without_budget_key_raises():
    n, _, _ = _make()
    with pytest.raises(PushPolicyError):
        await n.notify(DIS, "t", "b")


async def test_discretionary_claims_and_delivers():
    pl = _push_log()
    n, iface, _ = _make(push_log=pl)
    assert await n.notify(DIS, "t", "b", budget_key="k1") == "delivered"
    pl.try_claim.assert_awaited_once()
    assert pl.try_claim.call_args.args[:2] == (ATTENTION_PUSH_EVENT_KEY, "k1") or (
        pl.try_claim.call_args.kwargs.get("idempotency_key") == "k1"
    )
    pl.release_claim.assert_not_awaited()


async def test_discretionary_budget_full_is_suppressed_with_silent_frame():
    pl = _push_log(count=5)
    n, iface, store = _make(push_log=pl)
    assert await n.notify(DIS, "t", "b", budget_key="k1") == "suppressed_budget"
    assert store.create.call_args.kwargs["delivery"] == "suppressed"
    assert iface.push.call_args.args[0].delivery == "suppressed"
    pl.try_claim.assert_not_awaited()


async def test_discretionary_duplicate_key_creates_nothing():
    pl = _push_log(count=1, claim=False)
    n, iface, store = _make(push_log=pl)
    assert await n.notify(DIS, "t", "b", budget_key="k1") == "duplicate"
    store.create.assert_not_awaited()
    iface.push.assert_not_awaited()


async def test_discretionary_held_in_quiet_keeps_claim():
    pl = _push_log()
    n, iface, store = _make(push_log=pl, setting=QUIET, now=NIGHT)
    assert await n.notify(DIS, "t", "b", budget_key="k1") == "held"
    pl.release_claim.assert_not_awaited()
    assert store.create.call_args.kwargs["delivery"] == "held"


async def test_dedup_hours_hit_returns_deduped():
    store = _store()
    store.exists_recent = AsyncMock(return_value=True)
    n, iface, _ = _make(store=store)
    assert await n.notify(ACC, "t", "b", dedup_hours=24) == "deduped"
    store.create.assert_not_awaited()
    iface.push.assert_not_awaited()


async def test_no_store_returns_failed():
    iface = AsyncMock()
    n = ProactiveNotifier(iface, None)
    assert await n.notify(ACC, "t", "b") == "failed"
    iface.push.assert_not_awaited()


async def test_delivery_exception_releases_claim_and_marks_failed():
    pl = _push_log()
    n, iface, store = _make(push_log=pl)
    iface.push = AsyncMock(side_effect=RuntimeError("boom"))
    assert await n.notify(DIS, "t", "b", budget_key="k1") == "failed"
    pl.release_claim.assert_awaited_once()
    store.mark_failed.assert_awaited_once_with("n-1")


async def test_settings_store_error_means_not_quiet():
    n, iface, _ = _make(error=RuntimeError("db"), now=NIGHT)
    assert await n.notify(ACC, "t", "b") == "delivered"


async def test_actions_and_format_kept():
    n, iface, store = _make()
    await n.notify(
        ACC, "t", "b", format="html", actions=(Action("Go", "p", 1),)
    )
    kw = store.create.call_args.kwargs
    assert kw["format"] == "html"
    assert kw["actions"] == [{"label": "Go", "payload": "p", "row": 1}]
    assert iface.push.call_args.args[0].actions[0].label == "Go"


async def test_long_body_split_actions_on_last_chunk():
    n, iface, _ = _make()
    await n.notify(ACC, "t", "x" * 9000, actions=(Action("Go", "p"),))
    pushes = [c.args[0] for c in iface.push.call_args_list]
    assert len(pushes) == 3
    assert not pushes[0].actions and pushes[-1].actions


async def test_remaining_budget_math_and_floor():
    n, _, _ = _make(push_log=_push_log(count=2))
    assert await n.remaining_budget() == 3
    n, _, _ = _make(push_log=_push_log(count=9))
    assert await n.remaining_budget() == 0


async def test_remaining_budget_fails_open():
    pl = _push_log()
    pl.count_sent_within_hours = AsyncMock(side_effect=RuntimeError("db"))
    n, _, _ = _make(push_log=pl)
    assert await n.remaining_budget() == 5


async def test_deliver_held_releases_in_order_then_summary():
    held = [
        _row(id="a", urgency="high", delivery="held", title="A"),
        _row(id="b", urgency="low", delivery="held", title="B"),
    ]
    store = _store(held=held)
    n, iface, _ = _make(store=store, setting=QUIET, now=NOON)
    assert await n.deliver_held() == 2
    pushes = [c.args[0] for c in iface.push.call_args_list]
    assert [p.title for p in pushes[:2]] == ["A", "B"]
    assert all(p.buzz is False and p.delivery == "released" for p in pushes[:2])
    assert [c.args[0] for c in store.mark_released.call_args_list] == ["a", "b"]
    summary = pushes[2]
    assert summary.buzz is True and summary.urgency == "high"
    assert "held 2 updates" in summary.content
    assert store.create.call_args.kwargs["delivery"] == "delivered"
    assert summary.event_type == QUIET_HOURS_SUMMARY.event_type


async def test_deliver_held_zero_sends_nothing():
    n, iface, store = _make(store=_store(held=[]))
    assert await n.deliver_held() == 0
    iface.push.assert_not_awaited()
    store.create.assert_not_awaited()


async def test_deliver_held_while_quiet_does_nothing():
    store = _store(held=[_row(delivery="held")])
    n, iface, _ = _make(store=store, setting=QUIET, now=NIGHT)
    assert await n.deliver_held() == 0
    store.list_held.assert_not_awaited()
    iface.push.assert_not_awaited()
