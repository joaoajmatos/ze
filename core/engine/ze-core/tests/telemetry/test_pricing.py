import pytest

from ze_core.telemetry.pricing import (
    DEFAULT_PRICING,
    MODEL_PRICING,
    estimate_cost_usd,
)


def test_estimate_cost_for_listed_model():
    model = "anthropic/claude-sonnet-4-5"
    prompt_rate, completion_rate = MODEL_PRICING[model]
    cost = estimate_cost_usd(
        model, prompt_tokens=1_000_000, completion_tokens=1_000_000
    )
    assert cost == prompt_rate + completion_rate


def test_estimate_cost_falls_back_to_default_for_unlisted_model():
    cost = estimate_cost_usd(
        "some/unlisted-model", prompt_tokens=1_000_000, completion_tokens=1_000_000
    )
    assert cost == sum(DEFAULT_PRICING)


def test_estimate_cost_scales_with_token_count():
    model = "openai/gpt-4o-mini"
    cost = estimate_cost_usd(model, prompt_tokens=500_000, completion_tokens=0)
    prompt_rate, _ = MODEL_PRICING[model]
    assert cost == prompt_rate / 2


def test_system_one_is_priced_from_the_openrouter_generation_costs():
    """Derived 2026-10-16 from four real generations: cost = native prompt tokens x $0.042/M,
    completion free (1251 tokens -> $5.2542e-05, 1733 -> $7.2786e-05)."""
    assert estimate_cost_usd(
        "typesafe/jev-1.13-20260917", prompt_tokens=1251, completion_tokens=157
    ) == pytest.approx(5.2542e-05)
    assert estimate_cost_usd(
        "typesafe/jev-1.13-20260917", prompt_tokens=1733, completion_tokens=126
    ) == pytest.approx(7.2786e-05)


def test_system_one_configured_slug_and_dated_slug_share_a_price():
    configured = estimate_cost_usd("typesafe/jev-1.13", 1_000_000, 1_000_000)
    dated = estimate_cost_usd("typesafe/jev-1.13-20260917", 1_000_000, 1_000_000)
    assert configured == dated != sum(DEFAULT_PRICING)


def test_system_one_is_not_priced_at_the_conservative_default():
    cost = estimate_cost_usd(
        "typesafe/jev-1.13", prompt_tokens=1500, completion_tokens=150
    )
    default = estimate_cost_usd(
        "some/unlisted-model", prompt_tokens=1500, completion_tokens=150
    )
    assert cost < default / 100
