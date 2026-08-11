from ze_core.telemetry.pricing import (
    DEFAULT_PRICING,
    MODEL_PRICING,
    estimate_cost_usd,
)


def test_estimate_cost_for_listed_model():
    model = "anthropic/claude-sonnet-4-5"
    prompt_rate, completion_rate = MODEL_PRICING[model]
    cost = estimate_cost_usd(model, prompt_tokens=1_000_000, completion_tokens=1_000_000)
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
