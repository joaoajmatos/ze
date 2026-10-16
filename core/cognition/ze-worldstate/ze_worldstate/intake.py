"""Commitment intake — one System One request per conversation turn, then a code-owned commit.

`CommitmentIntake.admit` asks the commitment Choice plus the fact and loop questions in one batch,
merges the answers with what the turn already created (`commitment_judge.decide`), and hands back
an `IntakeAdmission`: the admitted facts, a loop commit to run after the episode exists, and the
outcome of linking a loop to a reminder or goal. Any failure falls back to the Haiku fact extractor
and the 109 Haiku loop gate (specs/phases/173-commitment-intake/contracts/commitment-judgment.md).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from ze_agents.client import LLMClient
from ze_agents.nested_tools import TurnCreation, tracking_earned, turn_creation
from ze_agents.system_one import SystemOneResult
from ze_agents.types import ToolCall
from ze_logging import get_logger
from ze_memory.extractor import (
    fact_extraction_model,
    gather_fact_proposals,
    is_trivial_turn,
    write_fact_values,
)
from ze_memory.types import FactAdmission

from ze_worldstate.admission import LoopInflow
from ze_worldstate.commitment_judge import (
    COMMITMENT_QUESTIONS,
    IntakeOutcome,
    build_state,
    commitment_intake_surface_config,
    decide,
)
from ze_worldstate.extraction import _resolve_entities
from ze_worldstate.loop_judge import CONVERSATION, LoopGateDecision
from ze_worldstate.matching import find_matching_loop
from ze_worldstate.types import LoopAdmission, SourceKey

log = get_logger(__name__)

_LIVE_STATES = ["suspected", "active", "drifting"]
_LOOP_KIND = {
    "resolve_loop": "resolve",
    "create_loop_declared": "create_declared",
    "create_loop_suspected": "create_suspected",
}


@dataclass
class LinkOutcome:
    kind: str
    linked: bool
    reason: str
    loop_id: UUID | None = None


@dataclass
class IntakeAdmission:
    """One conversation turn's intake. The node reads it by attribute; it never imports this type."""

    outcome: IntakeOutcome
    fact: FactAdmission | None = None
    loop: LoopAdmission | None = None
    link: LinkOutcome | None = None
    judgment: SystemOneResult | None = None
    question_kinds: dict[str, str] = field(default_factory=dict)
    consumed: frozenset[str] = frozenset()
    skip_reason: str | None = None

    @property
    def question_ids(self) -> tuple[str, ...]:
        return tuple(self.question_kinds)


class CommitmentIntake:
    def __init__(
        self,
        *,
        loop_inflow: LoopInflow,
        loop_store: Any,
        graph_store: Any,
        entity_resolver: Any,
        embedder: Any,
        system_one_client: Any = None,
        settings: Any = None,
    ) -> None:
        self._inflow = loop_inflow
        self._loop_store = loop_store
        self._graph_store = graph_store
        self._entity_resolver = entity_resolver
        self._embedder = embedder
        self._system_one = system_one_client
        self._settings = settings

    async def admit(
        self,
        configurable: dict,
        *,
        prompt: str,
        response: str,
        agent: str,
        tool_calls: list[ToolCall] | None = None,
    ) -> IntakeAdmission:
        """Never raises; any failure is a fallback admission."""
        calls = tool_calls or []
        tracked = tracking_earned(calls)
        source = self._source(configurable)
        if not prompt.strip() or is_trivial_turn(prompt):
            return IntakeAdmission(
                IntakeOutcome("hold", "trivial"),
                loop=self._loop_admission(
                    prompt, LoopGateDecision("hold", "trivial"), source
                ),
            )

        cfg = commitment_intake_surface_config(self._settings)
        skip_reason: str | None = None
        if not cfg.enabled:
            skip_reason = "disabled"
        elif not cfg.calibrated:
            log.warning("commitment_intake_uncalibrated")
            skip_reason = "uncalibrated"
        elif self._system_one is None:
            skip_reason = "unavailable"
        if skip_reason is not None:
            return await self._fallback(
                configurable,
                prompt,
                response,
                agent,
                source,
                tracked,
                skip_reason,
                None,
            )

        try:
            result = await self._system_one.evaluate(
                build_state(prompt, response), COMMITMENT_QUESTIONS, max_attempts=1
            )
        except Exception as exc:
            log.warning("commitment_intake_call_failed", error=str(exc))
            return await self._fallback(
                configurable, prompt, response, agent, source, tracked, "error", None
            )

        created = turn_creation(calls)
        outcome = decide(result, cfg, created, tracked)
        self._log(outcome, result, created)
        if outcome.kind == "fallback":
            if outcome.reason == "invalid_answer":
                log.warning("commitment_intake_invalid_answer")
            return await self._fallback(
                configurable,
                prompt,
                response,
                agent,
                source,
                tracked,
                outcome.reason,
                result,
                outcome=outcome,
            )
        return await self._apply(
            configurable, outcome, result, prompt, response, agent, source, created
        )

    def _source(self, configurable: dict) -> SourceKey | None:
        thread_id = configurable.get("thread_id")
        return SourceKey(CONVERSATION, str(thread_id)) if thread_id else None

    def _loop_admission(
        self,
        prompt: str,
        decision: LoopGateDecision,
        source: SourceKey | None,
        *,
        skip_reason: str | None = None,
    ) -> LoopAdmission:
        admission = self._inflow.finish(
            prompt, CONVERSATION, decision, skip_reason=skip_reason
        )
        admission.source = source
        return admission

    async def _fallback(
        self,
        configurable: dict,
        prompt: str,
        response: str,
        agent: str,
        source: SourceKey | None,
        tracked: bool,
        reason: str,
        result: SystemOneResult | None,
        *,
        outcome: IntakeOutcome | None = None,
    ) -> IntakeAdmission:
        """Today's Haiku paths: the fact extractor and the 109 loop gate."""
        fact = await self._haiku_facts(configurable, prompt, response, agent)
        fact.skip_reason = reason
        loop = None
        if not tracked:
            loop = self._loop_admission(
                prompt,
                LoopGateDecision("fallback", reason),
                source,
                skip_reason=reason,
            )
        return IntakeAdmission(
            outcome or IntakeOutcome("fallback", reason),
            fact=fact,
            loop=loop,
            judgment=result,
            question_kinds=(
                {qid: q.type for qid, q in COMMITMENT_QUESTIONS.items()}
                if result is not None
                else {}
            ),
            skip_reason=reason,
        )

    async def _haiku_facts(
        self, configurable: dict, prompt: str, response: str, agent: str
    ) -> FactAdmission:
        try:
            return await gather_fact_proposals(
                configurable, agent=agent, prompt=prompt, response=response
            )
        except Exception as exc:
            log.warning("commitment_intake_fact_fallback_failed", error=str(exc))
            return FactAdmission(path="none")

    async def _apply(
        self,
        configurable: dict,
        outcome: IntakeOutcome,
        result: SystemOneResult,
        prompt: str,
        response: str,
        agent: str,
        source: SourceKey | None,
        created: TurnCreation,
    ) -> IntakeAdmission:
        admission = IntakeAdmission(
            outcome,
            judgment=result,
            question_kinds={qid: q.type for qid, q in COMMITMENT_QUESTIONS.items()},
            consumed=outcome.consumed,
        )
        if outcome.kind == "persist_fact":
            admission.fact = await self._write_facts(
                configurable, outcome, result, prompt, response, agent
            )
        elif outcome.kind in _LOOP_KIND:
            admission.loop = self._loop_admission(
                prompt,
                LoopGateDecision(_LOOP_KIND[outcome.kind], outcome.reason),
                source,
            )
        elif outcome.kind == "link":
            admission.link = await self._link(prompt, outcome, created)
        return admission

    async def _write_facts(
        self,
        configurable: dict,
        outcome: IntakeOutcome,
        result: SystemOneResult,
        prompt: str,
        response: str,
        agent: str,
    ) -> FactAdmission:
        client: LLMClient | None = configurable.get("openrouter_client")
        facts = []
        if client is not None:
            settings = configurable.get("settings")
            config = getattr(settings, "config", settings)
            facts = await write_fact_values(
                client,
                prompt=prompt,
                response=response,
                family=outcome.family or "",
                model=fact_extraction_model(config),
            )
        for fact in facts:
            fact.agent = agent
        return FactAdmission(
            facts=facts,
            path="system_one",
            judgment=result,
            question_ids=tuple(COMMITMENT_QUESTIONS),
            consumed=outcome.consumed,
        )

    async def _link(
        self, prompt: str, outcome: IntakeOutcome, created: TurnCreation
    ) -> LinkOutcome:
        kind = outcome.link_kind or "reminder"
        raw = created.reminder_id if kind == "reminder" else created.goal_id
        try:
            target = UUID(str(raw))
        except (ValueError, TypeError):
            log.info("commitment_link_skipped", kind=kind, reason="no_id")
            return LinkOutcome(kind, False, "no_id")
        try:
            entity_ids = await _resolve_entities(self._entity_resolver, prompt)
            loop = await find_matching_loop(
                entity_ids,
                prompt[:200],
                loop_store=self._loop_store,
                graph_store=self._graph_store,
                embedder=self._embedder,
                states=_LIVE_STATES,
            )
            if loop is None:
                log.info("commitment_link_skipped", kind=kind, reason="no_match")
                return LinkOutcome(kind, False, "no_match")
            if getattr(loop, f"{kind}_id", None) is not None:
                log.info(
                    "commitment_link_skipped",
                    kind=kind,
                    reason="already_linked",
                    loop_id=str(loop.id),
                )
                return LinkOutcome(kind, False, "already_linked", loop.id)
            changed = await self._loop_store.link(loop.id, **{f"{kind}_id": target})
        except Exception as exc:
            log.warning("commitment_link_failed", kind=kind, error=str(exc))
            return LinkOutcome(kind, False, "error")
        log.info("commitment_linked", kind=kind, loop_id=str(loop.id), changed=changed)
        return LinkOutcome(
            kind, bool(changed), "linked" if changed else "not_live", loop.id
        )

    def _log(
        self, outcome: IntakeOutcome, result: SystemOneResult, created: TurnCreation
    ) -> None:
        commitment = result.answers.get("commitment")
        log.info(
            "commitment_intake_decision",
            kind=outcome.kind,
            reason=outcome.reason,
            consumed=sorted(outcome.consumed),
            choice=getattr(commitment, "choice", None),
            confidence=getattr(commitment, "confidence", None),
            created_reminder=created.reminder_id is not None,
            created_goal=created.goal_id is not None,
            latency_ms=result.latency_ms,
        )
