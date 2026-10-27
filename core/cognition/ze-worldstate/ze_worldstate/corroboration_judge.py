"""Corroboration judgment — one System One Noul, its surface config and the decision table.

`same_concern` asks whether an independent text is about the same unfinished matter as a suspected
loop. Pure code maps the score to promote, corroborate or not_same against two bars
(specs/phases/172-corroboration-promotion/contracts/corroboration-judgment.md).
Imports ze_agents types only; ze-worldstate never depends on ze-core.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Literal

from ze_agents.judgment import DecisionUse, SurfaceConfig
from ze_agents.system_one import (
    SystemOneQuestion,
    SystemOneResult,
    valid_noul,
)

from ze_worldstate import loop_judge

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
class CorroborationSurfaceConfig(SurfaceConfig):
    corroborate_hold: float | None = None
    promote_hold: float | None = None

    SURFACE: ClassVar[str] = "corroboration"
    BARS: ClassVar[dict[str, str]] = {
        "corroborate_hold": Q_SAME,
        "promote_hold": Q_SAME,
    }

    def consistent(self) -> bool:
        if self.corroborate_hold is None or self.promote_hold is None:
            return True
        return self.corroborate_hold <= self.promote_hold


CorroborationKind = Literal["promote", "corroborate", "not_same", "fallback"]


@dataclass(frozen=True)
class CorroborationDecision:
    kind: CorroborationKind
    reason: str
    score: float | None = None


def read_decision(decision: CorroborationDecision) -> DecisionUse:
    if decision.kind == "fallback":
        return DecisionUse(frozenset(), decision.reason)
    return DecisionUse(frozenset({Q_SAME}))


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
