"""Routing judgment — System One questions, state, surface config and the decision table.

E5 stays the shortlist. One batched request asks a Choice over the shortlist plus
``none``, a Noul ("more than one specialist?") and a Score (complexity). Pure code
turns the answers into trust / decompose / abstain / skip.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from ze_agents.system_one import SystemOneAnswer, SystemOneQuestion, SystemOneResult
from ze_logging import get_logger

log = get_logger(__name__)

USER_CAP = 2000
HISTORY_CAP = 1500
CONTEXT_CAP = 600
DEFAULT_SHORTLIST_K = 5
MIN_SHORTLIST = 2

NONE_KEY = "none"
Q_AGENT = "agent"
Q_MULTI = "multi_specialist"
Q_COMPLEXITY = "complexity"
QUESTION_IDS = (Q_AGENT, Q_MULTI, Q_COMPLEXITY)

_JUDGE_SUFFIX = "Judge the user's words; history and context are background only."

_NONE_CRITERION = "No listed agent can handle this request on its own."
_MULTI_INSTRUCTIONS = (
    "Does this request need more than one of these specialists, for example look "
    "something up and then act on the result? " + _JUDGE_SUFFIX
)
_AGENT_INSTRUCTIONS = (
    "Which one agent should handle this request? Answer none if no listed agent "
    "can handle it on its own. " + _JUDGE_SUFFIX
)
_COMPLEXITY_INSTRUCTIONS = (
    "How much work does this request need? Rate it from a simple lookup up to a "
    "multi-step task. " + _JUDGE_SUFFIX
)
_COMPLEXITY_LEVELS = [
    "lookup: a single fact or status check that needs no tool or one trivial read",
    "single_tool: one tool call or one clear action",
    "multi_hop: several dependent steps, tools or sources",
]
# The wire Score is the expected level index (0 = first level), not a [0, 1] probability.
COMPLEXITY_SCORE_MAX = float(len(_COMPLEXITY_LEVELS) - 1)


def normalise_complexity_score(score: Any) -> float | None:
    """Wire Score (0..COMPLEXITY_SCORE_MAX) → [0, 1]; ``None`` when malformed."""
    if (
        isinstance(score, bool)
        or not isinstance(score, (int, float))
        or math.isnan(score)
        or not 0.0 <= score <= COMPLEXITY_SCORE_MAX
    ):
        return None
    return score / COMPLEXITY_SCORE_MAX


@dataclass(frozen=True)
class RoutingSurfaceConfig:
    enabled: bool = False
    choice_trust: float | None = None
    multi_specialist_hold: float | None = None
    complexity_lookup_max: float | None = None
    shortlist_k: int = DEFAULT_SHORTLIST_K

    @property
    def calibrated(self) -> bool:
        return (
            self.enabled
            and self.choice_trust is not None
            and self.multi_specialist_hold is not None
        )


def _bar(value: Any, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        log.warning("routing_bar_invalid", bar=name)
        return None
    if math.isnan(value) or not 0.0 <= value <= 1.0:
        log.warning("routing_bar_invalid", bar=name)
        return None
    return float(value)


def _shortlist_k(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < MIN_SHORTLIST:
        return DEFAULT_SHORTLIST_K
    return value


def routing_surface_config(settings: Any) -> RoutingSurfaceConfig:
    config = (
        settings if isinstance(settings, dict) else getattr(settings, "config", None)
    )
    if not isinstance(config, dict):
        return RoutingSurfaceConfig()
    system_one = config.get("system_one")
    surfaces = system_one.get("surfaces") if isinstance(system_one, dict) else None
    block = surfaces.get("routing") if isinstance(surfaces, dict) else None
    if not isinstance(block, dict):
        return RoutingSurfaceConfig()
    return RoutingSurfaceConfig(
        enabled=block.get("enabled") is True,
        choice_trust=_bar(block.get("choice_trust"), "choice_trust"),
        multi_specialist_hold=_bar(
            block.get("multi_specialist_hold"), "multi_specialist_hold"
        ),
        complexity_lookup_max=_bar(
            block.get("complexity_lookup_max"), "complexity_lookup_max"
        ),
        shortlist_k=_shortlist_k(block.get("shortlist_k", DEFAULT_SHORTLIST_K)),
    )


def shortlist(ranked_agents: Sequence[str], k: int) -> list[str]:
    """Top-k of an E5-ranked list, clamped to the roster and never below two when two exist."""
    size = max(MIN_SHORTLIST, k)
    return list(ranked_agents[:size])


def build_questions(descriptions: Mapping[str, str]) -> dict[str, SystemOneQuestion]:
    """``descriptions`` maps shortlist agent name → description, in option order."""
    criteria = {name: desc.strip() for name, desc in descriptions.items()}
    criteria[NONE_KEY] = _NONE_CRITERION
    return {
        Q_AGENT: SystemOneQuestion(
            type="choice", instructions=_AGENT_INSTRUCTIONS, criteria=criteria
        ),
        Q_MULTI: SystemOneQuestion(type="noul", instructions=_MULTI_INSTRUCTIONS),
        Q_COMPLEXITY: SystemOneQuestion(
            type="score",
            instructions=_COMPLEXITY_INSTRUCTIONS,
            criteria=list(_COMPLEXITY_LEVELS),
        ),
    }


def build_state(user: str, history: str | None, context: str | None) -> dict[str, str]:
    state = {"user": user[:USER_CAP]}
    if history and history.strip():
        state["history"] = history[:HISTORY_CAP]
    if context and context.strip():
        state["context"] = context[:CONTEXT_CAP]
    return state


DecisionKind = Literal["trust", "decompose", "abstain", "skip"]


@dataclass(frozen=True)
class RoutingDecision:
    kind: DecisionKind
    reason: str
    agent: str | None = None
    confidence: float | None = None
    complexity: Literal["simple", "complex"] | None = None
    consumed: frozenset[str] = frozenset()


def _valid_choice(answer: SystemOneAnswer | None, allowed: Sequence[str]) -> bool:
    return (
        answer is not None
        and answer.type == "choice"
        and answer.choice is not None
        and answer.confidence is not None
        and (answer.choice == NONE_KEY or answer.choice in allowed)
    )


def _valid_noul(answer: SystemOneAnswer | None) -> bool:
    return (
        answer is not None
        and answer.type == "noul"
        and isinstance(answer.noul, (int, float))
        and not math.isnan(answer.noul)
    )


def _complexity(
    result: SystemOneResult, cfg: RoutingSurfaceConfig
) -> Literal["simple", "complex"] | None:
    """Score level → model tier. ``None`` means the regex classifier runs."""
    bar = cfg.complexity_lookup_max
    answer = result.answers.get(Q_COMPLEXITY)
    if bar is None or answer is None or answer.type != "score":
        return None
    score = normalise_complexity_score(answer.score)
    if score is None:
        return None
    return "simple" if score <= bar else "complex"


def decide(
    result: SystemOneResult, cfg: RoutingSurfaceConfig, names: Sequence[str]
) -> RoutingDecision:
    """Pure decision over one System One result (research R2, rules 3-7). Never raises.

    Rules 1-2 (surface off, bar unset, fewer than two agents) never reach a result.
    """
    if result.outcome == "skip":
        return RoutingDecision("skip", result.skip_reason or "error")
    trust_bar = cfg.choice_trust
    hold_bar = cfg.multi_specialist_hold
    if trust_bar is None or hold_bar is None:
        return RoutingDecision("skip", "uncalibrated")

    choice = result.answers.get(Q_AGENT)
    if choice is None or not _valid_choice(choice, names):
        return RoutingDecision("skip", "invalid_answer")
    peakedness = float(choice.confidence or 0.0)

    complexity = _complexity(result, cfg)
    extra = frozenset({Q_COMPLEXITY}) if complexity is not None else frozenset()

    if choice.choice == NONE_KEY:
        return RoutingDecision(
            "decompose",
            "choice_none",
            confidence=peakedness,
            complexity=complexity,
            consumed=frozenset({Q_AGENT}) | extra,
        )
    if peakedness < trust_bar:
        return RoutingDecision(
            "abstain", "choice_unsure", complexity=complexity, consumed=extra
        )

    noul = result.answers.get(Q_MULTI)
    if not _valid_noul(noul):
        return RoutingDecision(
            "trust",
            "trusted",
            agent=choice.choice,
            confidence=peakedness,
            complexity=complexity,
            consumed=frozenset({Q_AGENT}) | extra,
        )
    consumed = frozenset({Q_AGENT, Q_MULTI}) | extra
    if float(noul.noul or 0.0) >= hold_bar:
        return RoutingDecision(
            "decompose",
            "multi_specialist",
            confidence=peakedness,
            complexity=complexity,
            consumed=consumed,
        )
    return RoutingDecision(
        "trust",
        "trusted",
        agent=choice.choice,
        confidence=peakedness,
        complexity=complexity,
        consumed=consumed,
    )
