"""CostTracker.record charges the active script budget with a static-price estimate (197)."""

from __future__ import annotations

from ze_agents.scripts import ScriptBudget, current_script_budget
from ze_core.telemetry.pricing import DEFAULT_PRICING, estimate_cost_usd
from ze_core.telemetry.tracker import CostTracker


def _record(model: str = "anthropic/claude-haiku-4-5") -> None:
    CostTracker().record(model, 1000, 500, 1500, 10)


def test_record_inside_a_budget_charges_the_estimate() -> None:
    budget = ScriptBudget(limit_usd=1.0)
    token = current_script_budget.set(budget)
    try:
        _record()
    finally:
        current_script_budget.reset(token)
    assert budget.spent_usd == estimate_cost_usd(
        "anthropic/claude-haiku-4-5", 1000, 500
    )
    assert budget.spent_usd > 0


def test_record_outside_a_budget_charges_nothing() -> None:
    budget = ScriptBudget(limit_usd=1.0)
    _record()
    assert budget.spent_usd == 0.0
    assert current_script_budget.get() is None


def test_unknown_model_charges_the_default_price() -> None:
    budget = ScriptBudget(limit_usd=1.0)
    token = current_script_budget.set(budget)
    try:
        _record("someone/unknown-model")
    finally:
        current_script_budget.reset(token)
    prompt_rate, completion_rate = DEFAULT_PRICING
    expected = (1000 * prompt_rate + 500 * completion_rate) / 1_000_000
    assert budget.spent_usd == expected


def test_a_charge_failure_never_breaks_record() -> None:
    class _Broken:
        @property
        def exhausted(self):  # pragma: no cover
            return False

        @property
        def spent_usd(self):
            return 0.0

        @spent_usd.setter
        def spent_usd(self, value):
            raise RuntimeError("nope")

    token = current_script_budget.set(_Broken())  # type: ignore[arg-type]
    try:
        _record()
    finally:
        current_script_budget.reset(token)
