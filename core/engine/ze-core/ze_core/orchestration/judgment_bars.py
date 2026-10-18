"""The bar each judgment question is held to, read from the surface config in force."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ze_agents.system_one import parse_bar, surface_block
from ze_core.conversation.messages.types import JudgmentBar

# Question id -> bar name for the commitment intake surface. ze-core does not import ze-worldstate.
_INTAKE_BARS = {
    "commitment": "choice_hold",
    "family": "family_hold",
    "biography": "biography_hold",
    "is_open_concern": "loop_hold",
    "explicit_declaration": "explicit_hold",
    "resolves_existing": "resolves_hold",
}


def bar_map(
    surface: Any, bar_names: Mapping[str, str]
) -> dict[str, JudgmentBar | None]:
    """One entry per question; ``None`` while the bar is unset (the surface is uncalibrated)."""
    bars: dict[str, JudgmentBar | None] = {}
    for question_id, name in bar_names.items():
        value = getattr(surface, name, None)
        bars[question_id] = None if value is None else JudgmentBar(name, float(value))
    return bars


def intake_bars(settings: Any) -> dict[str, JudgmentBar | None]:
    block = surface_block(settings, "commitment_intake") or {}
    bars: dict[str, JudgmentBar | None] = {}
    for question_id, name in _INTAKE_BARS.items():
        value = parse_bar(block.get(name), name, event="commitment_intake_bar_invalid")
        bars[question_id] = None if value is None else JudgmentBar(name, value)
    return bars
