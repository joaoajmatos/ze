from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ze_core.telemetry.pricing import estimate_cost_usd
from ze_core.telemetry.store import CostStore


@dataclass
class SpendBudgetConfig:
    session_limit_usd: float | None
    daily_limit_usd: float | None


@dataclass
class BudgetStatus:
    within_budget: bool
    scope: Literal["session", "daily"] | None
    current_spend_usd: float
    limit_usd: float | None


class SpendBudgetChecker:
    """Real-time, token-estimated spend check against an opt-in budget config."""

    def __init__(self, cost_store: CostStore, config: SpendBudgetConfig) -> None:
        self._cost_store = cost_store
        self._config = config

    async def check(self, session_id: str) -> BudgetStatus:
        config = self._config
        if config.session_limit_usd is None and config.daily_limit_usd is None:
            return BudgetStatus(
                within_budget=True, scope=None, current_spend_usd=0.0, limit_usd=None
            )

        if config.session_limit_usd is not None:
            session_rows = await self._cost_store.fetch_session_usage(session_id)
            session_spend = _sum_usage(session_rows)
            if session_spend >= config.session_limit_usd:
                return BudgetStatus(
                    within_budget=False,
                    scope="session",
                    current_spend_usd=session_spend,
                    limit_usd=config.session_limit_usd,
                )

        if config.daily_limit_usd is not None:
            daily_rows = await self._cost_store.fetch_daily_usage()
            daily_spend = _sum_usage(daily_rows)
            if daily_spend >= config.daily_limit_usd:
                return BudgetStatus(
                    within_budget=False,
                    scope="daily",
                    current_spend_usd=daily_spend,
                    limit_usd=config.daily_limit_usd,
                )

        return BudgetStatus(
            within_budget=True, scope=None, current_spend_usd=0.0, limit_usd=None
        )


def _sum_usage(rows: list[dict]) -> float:
    return sum(
        estimate_cost_usd(
            row["model"], row["prompt_tokens"], row["completion_tokens"]
        )
        for row in rows
    )
