"""Corroboration judgment — one System One Noul, its surface config and the decision table.

`same_concern` asks whether an independent text is about the same unfinished matter as a suspected
loop. Pure code maps the score to promote, corroborate or not_same against two bars
(specs/phases/172-corroboration-promotion/contracts/corroboration-judgment.md).
Imports ze_agents types only; ze-worldstate never depends on ze-core.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import Any, Literal

from ze_agents.system_one import (
    SystemOneQuestion,
    SystemOneResult,
    parse_bar,
    surface_block,
    valid_noul,
)

from ze_worldstate import loop_judge

_bar = partial(parse_bar, event="corroboration_bar_invalid")

Q_SAME = "same_concern"

_LOOP_TITLE_CAP = 200

_SAME_INSTRUCTIONS = (
    "Is the text about the same unfinished matter as the open item named in `loop`? "
    "The same person, place or topic alone is not enough; it must be the same thing "
    "to do, decide, answer or follow up on."
)

QUESTION = SystemOneQuestion(type="noul", instructions=_SAME_INSTRUCTIONS)


def build_state(loop_title: str, text: str, inflow: str) -> dict[str, str]:
    return {"loop": loop_title.strip()[:_LOOP_TITLE_CAP], **loop_judge.build_state(text, inflow)}


@dataclass(frozen=True)
class CorroborationSurfaceConfig:
    enabled: bool = False
    corroborate_hold: float | None = None
    promote_hold: float | None = None

    @property
    def calibrated(self) -> bool:
        return (
            self.enabled
            and self.corroborate_hold is not None
            and self.promote_hold is not None
            and self.corroborate_hold <= self.promote_hold
        )


def corroboration_surface_config(settings: Any) -> CorroborationSurfaceConfig:
    block = surface_block(settings, "corroboration")
    if block is None:
        return CorroborationSurfaceConfig()
    return CorroborationSurfaceConfig(
        enabled=block.get("enabled") is True,
        corroborate_hold=_bar(block.get("corroborate_hold"), "corroborate_hold"),
        promote_hold=_bar(block.get("promote_hold"), "promote_hold"),
    )


CorroborationKind = Literal["promote", "corroborate", "not_same", "fallback"]


@dataclass(frozen=True)
class CorroborationDecision:
    kind: CorroborationKind
    reason: str
    score: float | None = None


def decide(
    result: SystemOneResult, cfg: CorroborationSurfaceConfig
) -> CorroborationDecision:
    """Pure decision over one result (contract rows 1, 2 and 4 to 8). Never raises."""
    if not cfg.enabled:
        return CorroborationDecision("fallback", "disabled")
    if not cfg.calibrated:
        return CorroborationDecision("fallback", "uncalibrated")
    if result.outcome == "skip":
        return CorroborationDecision("fallback", result.skip_reason or "error")
    answer = result.answers.get(Q_SAME)
    if not valid_noul(answer):
        return CorroborationDecision("fallback", "invalid_answer")
    score = float(answer.noul)  # type: ignore[union-attr, arg-type]
    if score >= cfg.promote_hold:  # type: ignore[operator]
        return CorroborationDecision("promote", "same_concern", score)
    if score >= cfg.corroborate_hold:  # type: ignore[operator]
        return CorroborationDecision("corroborate", "same_concern", score)
    return CorroborationDecision("not_same", "below_bar", score)
