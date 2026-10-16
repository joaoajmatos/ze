"""Tier judgment — which model an agent runs this turn.

Routing always assigns the agent's full model. After ``match_skills`` the
``choose_tier`` node asks one System One Noul (``needs_deep_reasoning``) about the task
at hand and swaps in ``model_simple`` only when the answer is at or below the bar.
Every other outcome keeps the full model.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

from ze_agents.model_resolution import resolve_model
from ze_agents.registry import get_enabled_agents
from ze_agents.system_one import SystemOneQuestion, SystemOneResult
from ze_logging import get_logger

from ze_core.routing.judge import parse_bar
from ze_core.routing.types import RoutingEnvelope, RoutingJudgment

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
class ComplexitySurfaceConfig:
    enabled: bool = False
    simple_max: float | None = None

    @property
    def calibrated(self) -> bool:
        return self.enabled and self.simple_max is not None


def complexity_surface_config(settings: Any) -> ComplexitySurfaceConfig:
    config = (
        settings if isinstance(settings, dict) else getattr(settings, "config", None)
    )
    if not isinstance(config, dict):
        return ComplexitySurfaceConfig()
    system_one = config.get("system_one")
    surfaces = system_one.get("surfaces") if isinstance(system_one, dict) else None
    block = surfaces.get("complexity") if isinstance(surfaces, dict) else None
    if not isinstance(block, dict):
        return ComplexitySurfaceConfig()
    return ComplexitySurfaceConfig(
        enabled=block.get("enabled") is True,
        simple_max=parse_bar(block.get("simple_max"), "simple_max"),
    )


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
    judgment: RoutingJudgment | None


def decide_tier(result: SystemOneResult, cfg: ComplexitySurfaceConfig) -> TierDecision:
    """Pure decision over one System One result. Never raises; every doubt is ``full``."""
    if result.outcome == "skip":
        return TierDecision("full", "skip", False)
    bar = cfg.simple_max
    answer = result.answers.get(Q_DEEP)
    noul = answer.noul if answer is not None and answer.type == "noul" else None
    if (
        bar is None
        or isinstance(noul, bool)
        or not isinstance(noul, (int, float))
        or math.isnan(noul)
        or not 0.0 <= noul <= 1.0
    ):
        return TierDecision("full", "invalid_answer", False)
    return TierDecision("simple" if noul <= bar else "full", "system_one", True)


class TierJudge:
    """One System One Noul per tierable turn. ``choose`` never raises."""

    def __init__(
        self, system_one_client: Any, surface: ComplexitySurfaceConfig, app_config: dict
    ) -> None:
        self._client = system_one_client
        self._surface = surface
        self._app_config = app_config
        self._uncalibrated_warned = False

    @property
    def surface(self) -> ComplexitySurfaceConfig:
        return self._surface

    @property
    def app_config(self) -> dict:
        return self._app_config

    def warn_uncalibrated_once(self) -> None:
        if not self._uncalibrated_warned:
            self._uncalibrated_warned = True
            log.warning("complexity_surface_uncalibrated")

    async def choose(
        self, envelope: RoutingEnvelope, tier_state: dict[str, str]
    ) -> TierOutcome:
        agent = envelope.subtasks[0].agent
        questions = build_tier_question()
        try:
            result = await self._client.evaluate(tier_state, questions, max_attempts=1)
        except Exception as exc:
            log.warning("tier_judgment_error", agent=agent, error=str(exc))
            result = SystemOneResult(outcome="skip", skip_reason="error")

        decision = decide_tier(result, self._surface)
        judgment = RoutingJudgment(
            result=result,
            question_kinds={qid: q.type for qid, q in questions.items()},
            consumed=frozenset({Q_DEEP}) if decision.consumed else frozenset(),
            skip_reason=(
                decision.decided_by if decision.decided_by == "invalid_answer" else None
            ),
        )
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
