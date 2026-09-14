"""Static per-model context-window table used by write_memory's compaction check.

No live lookup (no network call, no tiktoken dependency — research.md R3/R4): a
chars/4 estimate against this table's value is precise enough for a 70%-of-window
trigger. Model slugs are seeded from the models actually assigned across
apps/ze-api/config/config.yaml and agent `model` class attributes.
"""

from __future__ import annotations

MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    "anthropic/claude-sonnet-4-5": 200_000,
    "anthropic/claude-sonnet-4-6": 200_000,
    "anthropic/claude-haiku-4-5": 200_000,
    "openai/gpt-4o-mini": 128_000,
    "google/gemini-flash-1.5": 1_000_000,
}

DEFAULT_CONTEXT_WINDOW_TOKENS: int = 32_000
"""Conservative fallback for a model slug absent from the table (FR-005)."""


def get_context_window(model: str) -> int:
    return MODEL_CONTEXT_WINDOWS.get(model, DEFAULT_CONTEXT_WINDOW_TOKENS)
