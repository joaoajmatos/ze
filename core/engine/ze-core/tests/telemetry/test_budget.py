from __future__ import annotations

from unittest.mock import AsyncMock

from ze_core.telemetry.budget import SpendBudgetChecker, SpendBudgetConfig


def _make_checker(config: SpendBudgetConfig) -> tuple[SpendBudgetChecker, AsyncMock]:
    cost_store = AsyncMock()
    cost_store.fetch_session_usage = AsyncMock(return_value=[])
    cost_store.fetch_daily_usage = AsyncMock(return_value=[])
    checker = SpendBudgetChecker(cost_store=cost_store, config=config)
    return checker, cost_store


async def test_both_limits_none_short_circuits_no_query():
    checker, cost_store = _make_checker(
        SpendBudgetConfig(session_limit_usd=None, daily_limit_usd=None)
    )

    status = await checker.check(session_id="s1")

    assert status.within_budget is True
    cost_store.fetch_session_usage.assert_not_awaited()
    cost_store.fetch_daily_usage.assert_not_awaited()


async def test_session_spend_at_or_over_limit_blocks():
    checker, cost_store = _make_checker(
        SpendBudgetConfig(session_limit_usd=1.0, daily_limit_usd=None)
    )
    # anthropic/claude-sonnet-4-5: (3.00, 15.00) $/million -> 1M prompt tokens = $3.00
    cost_store.fetch_session_usage = AsyncMock(
        return_value=[
            {
                "model": "anthropic/claude-sonnet-4-5",
                "prompt_tokens": 1_000_000,
                "completion_tokens": 0,
            }
        ]
    )

    status = await checker.check(session_id="s1")

    assert status.within_budget is False
    assert status.scope == "session"
    assert status.current_spend_usd == 3.0
    assert status.limit_usd == 1.0


async def test_daily_spend_at_or_over_limit_blocks():
    checker, cost_store = _make_checker(
        SpendBudgetConfig(session_limit_usd=None, daily_limit_usd=2.0)
    )
    cost_store.fetch_daily_usage = AsyncMock(
        return_value=[
            {
                "model": "anthropic/claude-haiku-4-5",
                "prompt_tokens": 1_000_000,
                "completion_tokens": 1_000_000,
            }
        ]
    )

    status = await checker.check(session_id="s1")

    assert status.within_budget is False
    assert status.scope == "daily"
    assert status.current_spend_usd == 6.0
    assert status.limit_usd == 2.0


async def test_spend_under_both_limits_is_within_budget():
    checker, cost_store = _make_checker(
        SpendBudgetConfig(session_limit_usd=10.0, daily_limit_usd=20.0)
    )
    cost_store.fetch_session_usage = AsyncMock(
        return_value=[
            {
                "model": "openai/gpt-4o-mini",
                "prompt_tokens": 1000,
                "completion_tokens": 1000,
            }
        ]
    )
    cost_store.fetch_daily_usage = AsyncMock(
        return_value=[
            {
                "model": "openai/gpt-4o-mini",
                "prompt_tokens": 1000,
                "completion_tokens": 1000,
            }
        ]
    )

    status = await checker.check(session_id="s1")

    assert status.within_budget is True
