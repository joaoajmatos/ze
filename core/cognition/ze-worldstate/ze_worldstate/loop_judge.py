"""Loop-gate judgment — System One questions, state, surface config and the decision table.

Three independent Nouls decide whether a text opens, declares or resolves a loop. Pure code turns
the answers into a decision (specs/phases/168-loop-extraction-gate/contracts/loop-gate-judgment.md).
Imports ze_agents types only; ze-worldstate never depends on ze-core.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

from ze_agents.system_one import SystemOneAnswer, SystemOneQuestion, SystemOneResult
from ze_logging import get_logger

log = get_logger(__name__)

Q_CONCERN = "is_open_concern"
Q_EXPLICIT = "explicit_declaration"
Q_RESOLVES = "resolves_existing"

CONVERSATION = "conversation"

_STATE_KEY_AND_CAP: dict[str, tuple[str, int]] = {
    "conversation": ("user", 1000),
    "email": ("email", 1500),
    "calendar": ("event", 600),
    "ingestion": ("facts", 1500),
}

_CONCERN_INSTRUCTIONS = (
    "Does this text imply something the user, or someone in their life, still has to do, "
    "decide or follow up on, that is not yet done? Questions, small talk, notifications, "
    "marketing deadlines, routine events and reference facts do not."
)
_EXPLICIT_INSTRUCTIONS = (
    "Is the user themselves stating that they have to, need to, or want to be reminded "
    "to do this?"
)
_RESOLVES_INSTRUCTIONS = (
    "Does the text report that something the user needed to do is now done?"
)

LOOP_QUESTIONS: dict[str, SystemOneQuestion] = {
    Q_CONCERN: SystemOneQuestion(type="noul", instructions=_CONCERN_INSTRUCTIONS),
    Q_EXPLICIT: SystemOneQuestion(type="noul", instructions=_EXPLICIT_INSTRUCTIONS),
    Q_RESOLVES: SystemOneQuestion(type="noul", instructions=_RESOLVES_INSTRUCTIONS),
}


def supported_provenance(provenance: str) -> bool:
    return provenance in _STATE_KEY_AND_CAP


def questions_for(provenance: str) -> dict[str, SystemOneQuestion]:
    if provenance == CONVERSATION:
        return dict(LOOP_QUESTIONS)
    return {k: q for k, q in LOOP_QUESTIONS.items() if k != Q_EXPLICIT}


def capped_text(text: str, provenance: str) -> str:
    return text.strip()[: _STATE_KEY_AND_CAP[provenance][1]]


def build_state(text: str, provenance: str) -> dict[str, str]:
    key, _ = _STATE_KEY_AND_CAP[provenance]
    return {"source": provenance, key: capped_text(text, provenance)}


@dataclass(frozen=True)
class LoopGateSurfaceConfig:
    enabled: bool = False
    loop_hold: float | None = None
    explicit_hold: float | None = None
    resolves_hold: float | None = None

    @property
    def calibrated(self) -> bool:
        return (
            self.enabled
            and self.loop_hold is not None
            and self.explicit_hold is not None
            and self.resolves_hold is not None
        )


def _bar(value: Any, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        log.warning("loop_gate_bar_invalid", bar=name)
        return None
    if math.isnan(value) or not 0.0 <= value <= 1.0:
        log.warning("loop_gate_bar_invalid", bar=name)
        return None
    return float(value)


def loop_gate_surface_config(settings: Any) -> LoopGateSurfaceConfig:
    config = (
        settings if isinstance(settings, dict) else getattr(settings, "config", None)
    )
    if not isinstance(config, dict):
        return LoopGateSurfaceConfig()
    system_one = config.get("system_one")
    surfaces = system_one.get("surfaces") if isinstance(system_one, dict) else None
    block = surfaces.get("loop_gate") if isinstance(surfaces, dict) else None
    if not isinstance(block, dict):
        return LoopGateSurfaceConfig()
    return LoopGateSurfaceConfig(
        enabled=block.get("enabled") is True,
        loop_hold=_bar(block.get("loop_hold"), "loop_hold"),
        explicit_hold=_bar(block.get("explicit_hold"), "explicit_hold"),
        resolves_hold=_bar(block.get("resolves_hold"), "resolves_hold"),
    )


DecisionKind = Literal[
    "resolve", "create_declared", "create_suspected", "hold", "fallback"
]


@dataclass(frozen=True)
class LoopGateDecision:
    kind: DecisionKind
    reason: str
    consumed: frozenset[str] = frozenset()


def _valid_noul(answer: SystemOneAnswer | None) -> bool:
    return (
        answer is not None
        and answer.type == "noul"
        and isinstance(answer.noul, (int, float))
        and not isinstance(answer.noul, bool)
        and not math.isnan(answer.noul)
    )


def decide(
    result: SystemOneResult, cfg: LoopGateSurfaceConfig, provenance: str
) -> LoopGateDecision:
    """Pure decision over one result (contract rows 1 to 7). Never raises."""
    if result.outcome == "skip":
        return LoopGateDecision("fallback", result.skip_reason or "error")
    asked = tuple(questions_for(provenance))
    if not all(_valid_noul(result.answers.get(qid)) for qid in asked):
        return LoopGateDecision("fallback", "invalid_answer")
    loop_bar, explicit_bar, resolves_bar = (
        cfg.loop_hold,
        cfg.explicit_hold,
        cfg.resolves_hold,
    )
    if loop_bar is None or explicit_bar is None or resolves_bar is None:
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
    if provenance == CONVERSATION and score(Q_EXPLICIT) >= explicit_bar:
        return LoopGateDecision("create_declared", "explicit", consumed)
    return LoopGateDecision("create_suspected", "implied", consumed)
