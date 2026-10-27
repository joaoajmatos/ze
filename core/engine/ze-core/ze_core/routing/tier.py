"""Tier judgment — which model an agent runs this turn.

Routing always assigns the agent's full model. After ``match_skills`` the
``choose_tier`` node asks one System One Noul (``needs_deep_reasoning``) about the task
at hand and swaps in ``model_simple`` only when the answer is at or below the bar.
Every other outcome keeps the full model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Literal

from ze_agents.judgment import DecisionUse, Judgment, SurfaceConfig, judge
from ze_agents.model_resolution import resolve_model
from ze_agents.registry import get_enabled_agents
from ze_agents.system_one import (
    SystemOneClient,
    SystemOneQuestion,
    SystemOneResult,
    valid_noul,
)
from ze_logging import get_logger

from ze_core.routing.types import RoutingEnvelope

log = get_logger(__name__)

Tier = Literal["simple", "full"]
DecidedBy = Literal[
    "system_one",
    "off",
    "uncalibrated",
    "skip",
    "invalid_answer",
    "no_simple_model",
    "compound",
]

Q_DEEP = "needs_deep_reasoning"

TIER_INSTRUCTIONS = (
    "Will doing this task well need a stronger model: careful reasoning, weighing "
    "options, synthesis across several sources, planning, nuanced personal or "
    "emotional judgment, or several dependent steps? Answer no for greetings, "
    "thanks, acknowledgments, a single fact or status lookup, a short confirmation, "
    "or one routine action. Judge the task the user is trying to get done, not only "
    "their last message: use the conversation, recap, memory, focus and skill to "
    "work out what 'it', 'that plan', 'go ahead' or 'the other one' refers to."
)


@dataclass(frozen=True)
class ComplexitySurfaceConfig(SurfaceConfig):
    simple_max: float | None = None

    SURFACE: ClassVar[str] = "complexity"
    BARS: ClassVar[dict[str, str]] = {"simple_max": Q_DEEP}


def resolve_agent_model(agent_name: str, tier: Tier, app_config: dict) -> str:
    agent_cls = get_enabled_agents().get(agent_name)
    if agent_cls is None:
        declared = None
    elif tier == "simple" and agent_cls.model_simple:
        declared = agent_cls.model_simple
    else:
        declared = agent_cls.model
    return resolve_model(agent_name, declared, app_config)


def build_tier_question() -> dict[str, SystemOneQuestion]:
    return {Q_DEEP: SystemOneQuestion(type="noul", instructions=TIER_INSTRUCTIONS)}


@dataclass(frozen=True)
class TierDecision:
    tier: Tier
    decided_by: DecidedBy
    consumed: bool


@dataclass(frozen=True)
class TierOutcome:
    decision: TierDecision
    model: str
    judgment: Judgment | None


def decide_tier(result: SystemOneResult, cfg: ComplexitySurfaceConfig) -> TierDecision:
    """Pure decision over one System One result. Never raises; every doubt is ``full``."""
    if result.outcome == "skip":
        return TierDecision("full", "skip", False)
    bar = cfg.simple_max
    answer = result.answers.get(Q_DEEP)
    if bar is None or not valid_noul(answer):
        return TierDecision("full", "invalid_answer", False)
    return TierDecision("simple" if answer.noul <= bar else "full", "system_one", True)


def read_decision(decision: TierDecision) -> DecisionUse:
    return DecisionUse(
        consumed=frozenset({Q_DEEP}) if decision.consumed else frozenset(),
        unused_reason=(
            decision.decided_by if decision.decided_by == "invalid_answer" else None
        ),
    )


class TierJudge:
    """One System One Noul per tierable turn. ``choose`` never raises."""

    def __init__(
        self, system_one_client: Any, surface: ComplexitySurfaceConfig, app_config: dict
    ) -> None:
        self._client = system_one_client
        self._surface = surface
        self._app_config = app_config

    @property
    def client(self) -> SystemOneClient | None:
        return self._client

    @property
    def surface(self) -> ComplexitySurfaceConfig:
        return self._surface

    @property
    def app_config(self) -> dict:
        return self._app_config

    async def choose(
        self, envelope: RoutingEnvelope, tier_state: dict[str, str]
    ) -> TierOutcome:
        agent = envelope.subtasks[0].agent
        questions = build_tier_question()
        judgment, decision = await judge(
            self._client,
            self._surface,
            tier_state,
            questions,
            decide=lambda result: decide_tier(result, self._surface),
            read=read_decision,
        )
        result = judgment.result
        model = resolve_agent_model(agent, decision.tier, self._app_config)
        answer = result.answers.get(Q_DEEP)
        log.info(
            "tier_decided",
            agent=agent,
            tier=decision.tier,
            decided_by=decision.decided_by,
            noul=(
                round(answer.noul, 3)
                if answer is not None and isinstance(answer.noul, (int, float))
                else None
            ),
            latency_ms=result.latency_ms,
        )
        return TierOutcome(decision=decision, model=model, judgment=judgment)
