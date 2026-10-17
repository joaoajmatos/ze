from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from ze_agents.interface.types import Action
from ze_proactive.attention_budget import ATTENTION_PUSH_EVENT_KEY
from ze_proactive.errors import BudgetUnavailableError, PushPolicyError
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


def _store(held=None):
    store = AsyncMock()
    store.exists_recent = AsyncMock(return_value=False)
    store.create = AsyncMock(side_effect=lambda **kw: _row(**kw))
    store.list_held = AsyncMock(return_value=held or [])
    return store


def _stamps(count):
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [base + timedelta(minutes=i) for i in range(count)]


def _push_log(count=0, claim=True):
    pl = MagicMock()
    pl.window_sent_at = AsyncMock(return_value=_stamps(count))
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
    await n.notify(ACC, "t", "b", format="html", actions=(Action("Go", "p", 1),))
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
    pl.window_sent_at = AsyncMock(side_effect=RuntimeError("db"))
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


async def test_claim_error_fails_open_and_delivers():
    pl = _push_log()
    pl.try_claim = AsyncMock(side_effect=RuntimeError("lock timeout"))
    n, iface, _ = _make(push_log=pl)
    assert await n.notify(DIS, "t", "b", budget_key="k1") == "delivered"


async def test_discretionary_budget_full_in_quiet_is_suppressed_not_held():
    pl = _push_log(count=5)
    n, _, store = _make(push_log=pl, setting=QUIET, now=NIGHT)
    assert await n.notify(DIS, "t", "b", budget_key="k1") == "suppressed_budget"
    assert store.create.call_args.kwargs["delivery"] == "suppressed"


async def test_summary_not_held_by_quiet_race():
    held = [_row(id="a", urgency="normal", delivery="held")]
    n, iface, store = _make(store=_store(held=held), setting=QUIET, now=NOON)
    n._clock = iter([NOON, NIGHT, NIGHT, NIGHT]).__next__
    assert await n.deliver_held() == 1
    assert store.create.call_args.kwargs["delivery"] == "delivered"


CARD = PushKind("n_card", "accountability", "high", "tests", in_chat=False)


async def test_a_kind_shown_elsewhere_is_not_a_chat_message():
    n, iface, _ = _make()
    assert await n.notify(CARD, "t", "b") == "delivered"
    assert iface.push.call_args.args[0].in_chat is False


async def test_kinds_are_chat_messages_by_default():
    n, iface, _ = _make()
    await n.notify(ACC, "t", "b")
    assert iface.push.call_args.args[0].in_chat is True


async def test_target_parent_id_is_persisted_and_sent_in_the_frame():
    n, iface, store = _make()
    outcome = await n.notify(
        ACC,
        "t",
        "b",
        target_type="workflow_execution",
        target_id="ex-1",
        target_parent_id="wf-1",
    )
    assert outcome == "delivered"
    assert store.create.call_args.kwargs["target_parent_id"] == "wf-1"
    assert iface.push.call_args.args[0].target_parent_id == "wf-1"


async def test_target_parent_id_defaults_to_none():
    n, iface, store = _make()
    await n.notify(ACC, "t", "b")
    assert store.create.call_args.kwargs["target_parent_id"] is None
    assert iface.push.call_args.args[0].target_parent_id is None


async def test_held_notification_keeps_its_parent_through_quiet_hours_release():
    n, iface, store = _make(setting=QUIET, now=NIGHT)
    await n.notify(
        ACC,
        "t",
        "b",
        target_type="goal_gate",
        target_id="g1",
        target_parent_id="goal-1",
    )
    held_row = _row(
        target_type="goal_gate",
        target_id="g1",
        target_parent_id="goal-1",
        delivery="held",
    )

    released, released_iface, _ = _make(store=_store(held=[held_row]), now=NOON)
    released._store.mark_released = AsyncMock()
    await released.deliver_held()

    first = released_iface.push.call_args_list[0].args[0]
    assert first.target_parent_id == "goal-1"
    assert first.delivery == "released"


async def test_dedup_key_ignores_the_parent():
    n, _, store = _make()
    await n.notify(
        ACC,
        "t",
        "b",
        target_type="workflow_execution",
        target_id="ex-1",
        target_parent_id="wf-1",
        dedup_hours=1,
    )
    kwargs = store.exists_recent.call_args.kwargs
    assert set(kwargs) == {"event_type", "target_type", "target_id", "hours"}


async def test_budget_status_raises_without_push_log():
    n, _, _ = _make(push_log=None)
    with pytest.raises(BudgetUnavailableError):
        await n.budget_status()


async def test_budget_status_propagates_store_failure():
    pl = _push_log()
    pl.window_sent_at = AsyncMock(side_effect=RuntimeError("db"))
    n, _, _ = _make(push_log=pl)
    with pytest.raises(RuntimeError):
        await n.budget_status()


async def test_budget_status_reports_used_and_max():
    n, _, _ = _make(push_log=_push_log(count=2))
    status = await n.budget_status()
    assert (status.used, status.max_per_day, status.remaining) == (2, 5, 3)
