"""Commitment intake — one System One request per conversation turn, then a code-owned commit.

`CommitmentIntake.admit` asks the commitment Choice plus the fact and loop questions in one batch,
merges the answers with what the turn already created (`commitment_judge.decide`), and hands back
an `IntakeAdmission`: the admitted facts, a loop commit to run after the episode exists, and the
outcome of linking a loop to a reminder or goal. Any failure falls back to the Haiku fact extractor
and the 109 Haiku loop gate (specs/phases/173-commitment-intake/contracts/commitment-judgment.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from ze_agents.client import LLMClient
from ze_agents.judgment import Judgment, gate, judge
from ze_agents.nested_tools import TurnCreation, tracking_earned, turn_creation
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
    CommitmentIntakeSurfaceConfig,
    IntakeOutcome,
    build_state,
    decide,
    read_decision,
)
from ze_worldstate.extraction import resolve_entities
from ze_worldstate.loop_judge import LoopGateDecision
from ze_worldstate.matching import find_matching_loop
from ze_worldstate.types import LoopAdmission, LoopProvenance, SourceKey

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
    links: tuple[LinkOutcome, ...] = ()
    judgment: Judgment | None = None


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
        created = turn_creation(calls)
        suppress_loop = tracked or bool(created.reminder_id or created.goal_id)
        source = self._source(configurable)
        if not prompt.strip() or is_trivial_turn(prompt):
            return IntakeAdmission(
                IntakeOutcome("hold", "trivial"),
                loop=self._loop_admission(
                    prompt, LoopGateDecision("hold", "trivial"), source
                ),
            )

        cfg = CommitmentIntakeSurfaceConfig.from_settings(self._settings)
        reason = gate(cfg, self._system_one)
        if reason is not None:
            return await self._fallback(
                configurable,
                prompt,
                response,
                agent,
                source,
                suppress_loop,
                reason,
                None,
            )

        judgment, outcome = await judge(
            self._system_one,
            cfg,
            build_state(prompt, response),
            COMMITMENT_QUESTIONS,
            lambda result: decide(result, cfg, created, tracked),
            read_decision,
        )
        self._log(outcome, judgment, created)
        if outcome.kind == "fallback":
            if outcome.reason == "invalid_answer":
                log.warning("commitment_intake_invalid_answer")
            return await self._fallback(
                configurable,
                prompt,
                response,
                agent,
                source,
                suppress_loop,
                outcome.reason,
                judgment,
                outcome=outcome,
            )
        return await self._apply(
            configurable, outcome, judgment, prompt, response, agent, source, created
        )

    def _source(self, configurable: dict) -> SourceKey | None:
        thread_id = configurable.get("thread_id")
        return (
            SourceKey(LoopProvenance.CONVERSATION, str(thread_id))
            if thread_id
            else None
        )

    def _loop_admission(
        self,
        prompt: str,
        decision: LoopGateDecision,
        source: SourceKey | None,
    ) -> LoopAdmission:
        admission = self._inflow.finish(prompt, LoopProvenance.CONVERSATION, decision)
        admission.source = source
        return admission

    async def _fallback(
        self,
        configurable: dict,
        prompt: str,
        response: str,
        agent: str,
        source: SourceKey | None,
        suppress_loop: bool,
        reason: str,
        judgment: Judgment | None,
        *,
        outcome: IntakeOutcome | None = None,
    ) -> IntakeAdmission:
        """Today's Haiku paths: the fact extractor and the 109 loop gate."""
        fact = await self._haiku_facts(configurable, prompt, response, agent)
        loop = None
        if not suppress_loop:
            loop = self._loop_admission(
                prompt, LoopGateDecision("fallback", reason), source
            )
        return IntakeAdmission(
            outcome or IntakeOutcome("fallback", reason),
            fact=fact,
            loop=loop,
            judgment=judgment,
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
        judgment: Judgment,
        prompt: str,
        response: str,
        agent: str,
        source: SourceKey | None,
        created: TurnCreation,
    ) -> IntakeAdmission:
        admission = IntakeAdmission(outcome, judgment=judgment)
        if outcome.kind == "persist_fact":
            admission.fact = await self._write_facts(
                configurable, outcome, prompt, response, agent
            )
        elif outcome.kind in _LOOP_KIND:
            admission.loop = self._loop_admission(
                prompt,
                LoopGateDecision(_LOOP_KIND[outcome.kind], outcome.reason),
                source,
            )
        elif outcome.kind == "link":
            admission.links = await self._link(prompt, created)
        return admission

    async def _write_facts(
        self,
        configurable: dict,
        outcome: IntakeOutcome,
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
        return FactAdmission(facts=facts, path="system_one")

    async def _link(
        self, prompt: str, created: TurnCreation
    ) -> tuple[LinkOutcome, ...]:
        """Link every reminder or goal the turn created to the one live loop it matches."""
        outcomes: list[LinkOutcome] = []
        targets: list[tuple[str, UUID]] = []
        for kind, raw in (("reminder", created.reminder_id), ("goal", created.goal_id)):
            if not raw:
                continue
            try:
                targets.append((kind, UUID(str(raw))))
            except (ValueError, TypeError):
                log.info("commitment_link_skipped", kind=kind, reason="no_id")
                outcomes.append(LinkOutcome(kind, False, "no_id"))
        if not targets:
            return tuple(outcomes)
        try:
            entity_ids = await resolve_entities(self._entity_resolver, prompt)
            loop = await find_matching_loop(
                entity_ids,
                prompt[:200],
                loop_store=self._loop_store,
                graph_store=self._graph_store,
                embedder=self._embedder,
                states=_LIVE_STATES,
                verify_similarity=True,
            )
        except Exception as exc:
            log.warning("commitment_link_failed", error=str(exc))
            return tuple(
                outcomes + [LinkOutcome(k, False, "error") for k, _ in targets]
            )
        for kind, target in targets:
            outcomes.append(await self._link_one(loop, kind, target))
        return tuple(outcomes)

    async def _link_one(self, loop: Any, kind: str, target: UUID) -> LinkOutcome:
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
        try:
            changed = await self._loop_store.link(loop.id, **{f"{kind}_id": target})
        except Exception as exc:
            log.warning("commitment_link_failed", kind=kind, error=str(exc))
            return LinkOutcome(kind, False, "error")
        log.info("commitment_linked", kind=kind, loop_id=str(loop.id), changed=changed)
        return LinkOutcome(
            kind, bool(changed), "linked" if changed else "unchanged", loop.id
        )

    def _log(
        self, outcome: IntakeOutcome, judgment: Judgment, created: TurnCreation
    ) -> None:
        result = judgment.result
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
