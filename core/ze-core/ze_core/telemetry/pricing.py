"""Static per-model $/token pricing table used by the spend budget gate.

No live OpenRouter pricing lookup (no network call) — a static table is precise
enough for a soft budget-hold decision, mirroring `openrouter/context_windows.py`'s
own static-table precedent (Phase 112). Model slugs are seeded from the models
actually assigned across apps/ze-api/config/config.yaml and agent `model` class
attributes. Rates sourced from published OpenRouter pricing as of 2026-08-11 —
re-check periodically, this table goes stale like any other static price list.
"""

from __future__ import annotations

MODEL_PRICING: dict[str, tuple[float, float]] = {
    # model_slug -> (prompt_usd_per_million, completion_usd_per_million)
    "anthropic/claude-sonnet-4-5": (3.00, 15.00),
    "anthropic/claude-sonnet-4-6": (3.00, 15.00),
    "anthropic/claude-haiku-4-5": (1.00, 5.00),
    "openai/gpt-4o-mini": (0.15, 0.60),
    "google/gemini-flash-1.5": (0.075, 0.30),
}

DEFAULT_PRICING: tuple[float, float] = (5.00, 15.00)
"""Conservative fallback for a model slug absent from the table."""


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    prompt_rate, completion_rate = MODEL_PRICING.get(model, DEFAULT_PRICING)
    return (prompt_tokens * prompt_rate + completion_tokens * completion_rate) / 1_000_000
