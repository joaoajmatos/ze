from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from ze_finance.jobs.recurring import RecurringDetectionJob
from ze_finance.push_kinds import (
    FINANCE_PRICE_CHANGE,
    FINANCE_RECURRING_NEW,
    FINANCE_STALE_NUDGE,
)
from ze_finance.recurring.types import (
    RecurringExpense,
    RecurringStatus,
    UpsertResult,
)
from ze_sdk.proactive import OncePer


def _account(name="Barclays", source_id="csv:barclays"):
    account = MagicMock()
    account.id = "acc-1"
    account.name = name
    account.source_id = source_id
    return account


def _expense(*, amount="9.99", previous=None, merchant="Netflix"):
    return RecurringExpense(
        normalised_key="netflix",
        account_id="acc-1",
        merchant_display=merchant,
        amount=Decimal(amount),
        currency="EUR",
        interval_days=30,
        category="subscription",
        status=RecurringStatus.DETECTED,
        first_seen_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
        occurrence_count=3,
        previous_amount=Decimal(previous) if previous else None,
    )


def _make_job(*, last_settled_at, notifier=None, upsert_result=None, candidates=None):
    portfolio = AsyncMock()
    portfolio.list_accounts = AsyncMock(return_value=[_account()])

    transactions = AsyncMock()
    transactions.get_last_settled_at = AsyncMock(return_value=last_settled_at)
    transactions.get = AsyncMock(return_value=[])

    recurring = AsyncMock()
    recurring.get_last_nudge_at = AsyncMock(return_value=None)
    recurring.upsert_detected = AsyncMock(
        return_value=upsert_result or UpsertResult([], [])
    )
    recurring.record_nudge = AsyncMock()

    detector = AsyncMock()
    detector.detect_transactions = AsyncMock(return_value=candidates or [])

    n = notifier if notifier is not None else AsyncMock()
    if notifier is None:
        n.notify = AsyncMock(return_value="delivered")

    job = RecurringDetectionJob(
        portfolio_store=portfolio,
        transaction_store=transactions,
        recurring_store=recurring,
        notifier=n,
        detector=detector,
        staleness_days=35,
        nudge_cooldown_days=14,
        lookback_days=90,
    )
    return job, n, recurring


def _stale_at() -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=40)


def _fresh_at() -> datetime:
    return datetime.now(timezone.utc)


async def test_stale_csv_account_nudges_and_records_nudge():
    job, notifier, recurring = _make_job(last_settled_at=_stale_at())
    await job.run()

    notifier.notify.assert_awaited_once()
    call = notifier.notify.call_args
    assert call.args[0] is FINANCE_STALE_NUDGE
    assert call.args[1] == "Bank statement needed"
    assert "Barclays" in call.args[2]
    assert call.kwargs["once_per"] == OncePer(
        f"finance_stale:acc-1:{date.today().isoformat()}"
    )
    recurring.record_nudge.assert_awaited_once_with("acc-1")


async def test_stale_nudge_not_recorded_when_suppressed():
    notifier = AsyncMock()
    notifier.notify = AsyncMock(return_value="suppressed_budget")
    job, _, recurring = _make_job(last_settled_at=_stale_at(), notifier=notifier)
    await job.run()

    notifier.notify.assert_awaited_once()
    recurring.record_nudge.assert_not_awaited()


async def test_new_candidates_notify_new_recurring():
    candidate = _expense()
    job, notifier, _ = _make_job(
        last_settled_at=_fresh_at(),
        upsert_result=UpsertResult(new_candidates=[candidate], price_changed=[]),
        candidates=[candidate],
    )
    await job.run()

    notifier.notify.assert_awaited_once()
    call = notifier.notify.call_args
    assert call.args[0] is FINANCE_RECURRING_NEW
    assert call.args[1] == "New recurring expenses"
    assert call.kwargs["once_per"] == OncePer(
        f"finance_new:acc-1:{date.today().isoformat()}"
    )


async def test_price_change_notifies():
    changed = _expense(amount="12.99", previous="9.99")
    job, notifier, _ = _make_job(
        last_settled_at=_fresh_at(),
        upsert_result=UpsertResult(new_candidates=[], price_changed=[changed]),
        candidates=[changed],
    )
    await job.run()

    notifier.notify.assert_awaited_once()
    call = notifier.notify.call_args
    assert call.args[0] is FINANCE_PRICE_CHANGE
    assert call.args[1] == "Price change"
    assert "Netflix" in call.args[2]
    assert call.kwargs["once_per"] == OncePer("finance_price:netflix:12.99")
