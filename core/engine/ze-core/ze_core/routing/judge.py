"""Routing judgment — System One questions, state, surface config and the decision table.

E5 stays the shortlist. One batched request asks a Choice over the shortlist plus
``none`` and a Noul ("more than one specialist?"). Pure code turns the answers into
trust / decompose / abstain / skip.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import partial
from typing import Any, Literal

from ze_agents.system_one import (
    SystemOneQuestion,
    SystemOneResult,
    parse_bar,
    surface_block,
    valid_choice,
    valid_noul,
)
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

_JUDGE_SUFFIX = "Judge the user's words; history and context are background only."

_NONE_CRITERION = (
    "No listed agent can do this alone: the capability does not exist (for example "
    "controlling a device), or it needs more than one agent, or it is none of the "
    "listed agents' work."
)
_MULTI_INSTRUCTIONS = (
    "Does this request need more than one of these specialists, for example look "
    "something up and then act on the result? " + _JUDGE_SUFFIX
)
_AGENT_INSTRUCTIONS = (
    "Which one agent should handle this request? When the request needs facts, "
    "comparisons, recent information or step-by-step help, prefer the agent that "
    "searches the web or uses tools over one that would answer from its own "
    "knowledge. Answer none if no listed agent can do it alone. " + _JUDGE_SUFFIX
)


@dataclass(frozen=True)
class RoutingSurfaceConfig:
    enabled: bool = False
    choice_trust: float | None = None
    multi_specialist_hold: float | None = None
    shortlist_k: int = DEFAULT_SHORTLIST_K

    @property
    def calibrated(self) -> bool:
        return (
            self.enabled
            and self.choice_trust is not None
            and self.multi_specialist_hold is not None
        )


_bar = partial(parse_bar, event="routing_bar_invalid")


def _shortlist_k(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < MIN_SHORTLIST:
        return DEFAULT_SHORTLIST_K
    return value


def routing_surface_config(settings: Any) -> RoutingSurfaceConfig:
    block = surface_block(settings, "routing")
    if block is None:
        return RoutingSurfaceConfig()
    return RoutingSurfaceConfig(
        enabled=block.get("enabled") is True,
        choice_trust=_bar(block.get("choice_trust"), "choice_trust"),
        multi_specialist_hold=_bar(
            block.get("multi_specialist_hold"), "multi_specialist_hold"
        ),
        shortlist_k=_shortlist_k(block.get("shortlist_k", DEFAULT_SHORTLIST_K)),
    )


def shortlist(ranked_agents: Sequence[str], k: int) -> list[str]:
    """Top-k of an E5-ranked list, clamped to the roster and never below two when two exist."""
    size = max(MIN_SHORTLIST, k)
    return list(ranked_agents[:size])


def criterion_for(agent_cls: Any) -> str:
    """The Choice text for an agent: ``routing_criteria`` when set, else ``description``."""
    criteria = (getattr(agent_cls, "routing_criteria", "") or "").strip()
    return criteria or agent_cls.description.strip()


def build_questions(
    criteria_by_agent: Mapping[str, str],
) -> dict[str, SystemOneQuestion]:
    """``criteria_by_agent`` maps shortlist agent name → Choice text, in option order."""
    criteria = {name: text.strip() for name, text in criteria_by_agent.items()}
    criteria[NONE_KEY] = _NONE_CRITERION
    return {
        Q_AGENT: SystemOneQuestion(
            type="choice", instructions=_AGENT_INSTRUCTIONS, criteria=criteria
        ),
        Q_MULTI: SystemOneQuestion(type="noul", instructions=_MULTI_INSTRUCTIONS),
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
    consumed: frozenset[str] = frozenset()


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
    if choice is None or not valid_choice(choice, [*names, NONE_KEY]):
        return RoutingDecision("skip", "invalid_answer")
    peakedness = float(choice.confidence or 0.0)

    if choice.choice == NONE_KEY:
        return RoutingDecision(
            "decompose",
            "choice_none",
            confidence=peakedness,
            consumed=frozenset({Q_AGENT}),
        )
    if peakedness < trust_bar:
        return RoutingDecision("abstain", "choice_unsure")

    noul = result.answers.get(Q_MULTI)
    if not valid_noul(noul, unit_range=False):
        return RoutingDecision(
            "trust",
            "trusted",
            agent=choice.choice,
            confidence=peakedness,
            consumed=frozenset({Q_AGENT}),
        )
    consumed = frozenset({Q_AGENT, Q_MULTI})
    if float(noul.noul or 0.0) >= hold_bar:
        return RoutingDecision(
            "decompose",
            "multi_specialist",
            confidence=peakedness,
            consumed=consumed,
        )
    return RoutingDecision(
        "trust",
        "trusted",
        agent=choice.choice,
        confidence=peakedness,
        consumed=consumed,
    )
