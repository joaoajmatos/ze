"""Loop-gate judgment — System One questions, state, surface config and the decision table.

Two independent Nouls decide whether a text opens or resolves a loop on the email, calendar and
ingestion inflows (conversation turns use commitment_judge). Pure code turns the answers into a
decision (specs/phases/168-loop-extraction-gate/contracts/loop-gate-judgment.md).
Imports ze_agents types only; ze-worldstate never depends on ze-core.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import Any

from ze_agents.system_one import (
    SystemOneQuestion,
    SystemOneResult,
    parse_bar,
    surface_block,
    valid_noul,
)

from ze_worldstate.decision import CommitDecision

_bar = partial(parse_bar, event="loop_gate_bar_invalid")

Q_CONCERN = "is_open_concern"
Q_RESOLVES = "resolves_existing"

_STATE_KEY_AND_CAP: dict[str, tuple[str, int]] = {
    "conversation": ("user", 1000),
    "email": ("email", 1500),
    "calendar": ("event", 600),
    "ingestion": ("facts", 1500),
}

CONCERN_INSTRUCTIONS = (
    "Does this text show something the user still has to do, decide, answer or follow up on, "
    "or something that someone is waiting on the user for, that is not yet done? "
    "Questions, small talk, notifications, marketing deadlines, routine events and "
    "reference facts do not."
)
_RESOLVES_INSTRUCTIONS = (
    "Does the text report that something the user needed to do is now done?"
)

LOOP_QUESTIONS: dict[str, SystemOneQuestion] = {
    Q_CONCERN: SystemOneQuestion(type="noul", instructions=CONCERN_INSTRUCTIONS),
    Q_RESOLVES: SystemOneQuestion(type="noul", instructions=_RESOLVES_INSTRUCTIONS),
}


def supported_provenance(provenance: str) -> bool:
    return provenance in _STATE_KEY_AND_CAP


def capped_text(text: str, provenance: str) -> str:
    return text.strip()[: _STATE_KEY_AND_CAP[provenance][1]]


def build_state(text: str, provenance: str) -> dict[str, str]:
    key, _ = _STATE_KEY_AND_CAP[provenance]
    return {"source": provenance, key: capped_text(text, provenance)}


@dataclass(frozen=True)
class LoopGateSurfaceConfig:
    enabled: bool = False
    loop_hold: float | None = None
    resolves_hold: float | None = None

    @property
    def calibrated(self) -> bool:
        return (
            self.enabled
            and self.loop_hold is not None
            and self.resolves_hold is not None
        )


def loop_gate_surface_config(settings: Any) -> LoopGateSurfaceConfig:
    block = surface_block(settings, "loop_gate")
    if block is None:
        return LoopGateSurfaceConfig()
    return LoopGateSurfaceConfig(
        enabled=block.get("enabled") is True,
        loop_hold=_bar(block.get("loop_hold"), "loop_hold"),
        resolves_hold=_bar(block.get("resolves_hold"), "resolves_hold"),
    )


def decide(
    result: SystemOneResult, cfg: LoopGateSurfaceConfig, provenance: str
) -> CommitDecision:
    """Pure decision over one result (contract rows 1 to 7). Never raises. Never declares."""
    if result.outcome == "skip":
        return CommitDecision("fallback", result.skip_reason or "error")
    asked = tuple(LOOP_QUESTIONS)
    if not all(valid_noul(result.answers.get(qid)) for qid in asked):
        return CommitDecision("fallback", "invalid_answer")
    loop_bar, resolves_bar = cfg.loop_hold, cfg.resolves_hold
    if loop_bar is None or resolves_bar is None:
        return CommitDecision("fallback", "uncalibrated")

    def score(qid: str) -> float:
        return float(result.answers[qid].noul or 0.0)

    if score(Q_RESOLVES) >= resolves_bar:
        return CommitDecision("resolve", "resolves", frozenset({Q_RESOLVES}))
    if score(Q_CONCERN) < loop_bar:
        return CommitDecision(
            "hold", "not_open_concern", frozenset({Q_CONCERN, Q_RESOLVES})
        )
    consumed = frozenset(asked)
    return CommitDecision("create_suspected", "implied", consumed)
