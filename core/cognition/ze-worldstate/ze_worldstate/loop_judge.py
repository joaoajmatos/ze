"""Loop-gate judgment — System One questions, state, surface config and the decision table.

Two independent Nouls decide whether a text opens or resolves a loop on the email, calendar and
ingestion inflows (conversation turns use commitment_judge). Pure code turns the answers into a
decision (specs/phases/168-loop-extraction-gate/contracts/loop-gate-judgment.md).
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
class LoopGateSurfaceConfig(SurfaceConfig):
    loop_hold: float | None = None
    resolves_hold: float | None = None

    SURFACE: ClassVar[str] = "loop_gate"
    BARS: ClassVar[dict[str, str]] = {
        "loop_hold": Q_CONCERN,
        "resolves_hold": Q_RESOLVES,
    }


DecisionKind = Literal[
    "resolve", "create_declared", "create_suspected", "hold", "fallback"
]


@dataclass(frozen=True)
class LoopGateDecision:
    kind: DecisionKind
    reason: str
    consumed: frozenset[str] = frozenset()


def read_decision(decision: LoopGateDecision) -> DecisionUse:
    return DecisionUse(
        decision.consumed,
        decision.reason if decision.kind == "fallback" else None,
    )


def decide(
    result: SystemOneResult, cfg: LoopGateSurfaceConfig, provenance: str
) -> LoopGateDecision:
    """Pure decision over one result (contract rows 1 to 7). Never raises."""
    if result.outcome == "skip":
        return LoopGateDecision("fallback", result.skip_reason or "error")
    asked = tuple(LOOP_QUESTIONS)
    if not all(valid_noul(result.answers.get(qid)) for qid in asked):
        return LoopGateDecision("fallback", "invalid_answer")
    loop_bar, resolves_bar = cfg.loop_hold, cfg.resolves_hold
    if loop_bar is None or resolves_bar is None:
        return LoopGateDecision("fallback", "uncalibrated")

    def score(qid: str) -> float:
        return float(result.answers[qid].noul or 0.0)

    if score(Q_RESOLVES) >= resolves_bar:
        return LoopGateDecision("resolve", "resolves", frozenset({Q_RESOLVES}))
    if score(Q_CONCERN) < loop_bar:
        return LoopGateDecision(
            "hold", "not_open_concern", frozenset({Q_CONCERN, Q_RESOLVES})
        )
    consumed = frozenset(asked)
    return LoopGateDecision("create_suspected", "implied", consumed)
