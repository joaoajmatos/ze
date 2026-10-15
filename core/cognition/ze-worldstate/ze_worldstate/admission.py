"""Loop gate — one System One request per qualifying text, then a code-owned commit.

`LoopInflow` judges a text (conversation, email, calendar, ingestion) with three Nouls, decides in
pure code, and hands back a `LoopAdmission` whose `commit` creates or closes the loop. Any failure
falls back to the 109 Haiku gate (FR-012, FR-013).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ze_agents.client import LLMClient
from ze_logging import get_logger
from ze_memory.extractor import is_trivial_turn
from ze_plugin.contribution import EvidenceRef

from ze_worldstate import loop_judge
from ze_worldstate.extraction import DEFAULT_EXTRACTION_MODEL, propose_loop_candidates
from ze_worldstate.loop_judge import (
    CONVERSATION,
    LoopGateDecision,
    loop_gate_surface_config,
)
from ze_worldstate.types import LoopAdmission, SourceKey, TitleWriterResult

__all__ = ["LoopAdmission", "LoopInflow", "TitleWriterResult"]

log = get_logger(__name__)


class LoopInflow:
    def __init__(
        self,
        *,
        loop_store: Any,
        graph_store: Any,
        entity_resolver: Any,
        llm_client: LLMClient,
        embedder: Any,
        memory_store: Any = None,
        collision_store: Any = None,
        nli_client: Any = None,
        system_one_client: Any = None,
        settings: Any = None,
        model: str = DEFAULT_EXTRACTION_MODEL,
    ) -> None:
        self._loop_store = loop_store
        self._graph_store = graph_store
        self._entity_resolver = entity_resolver
        self._llm = llm_client
        self._embedder = embedder
        self._memory_store = memory_store
        self._collision_store = collision_store
        self._nli_client = nli_client
        self._system_one = system_one_client
        self._settings = settings
        self._model = model

    async def admit(self, configurable: dict, *, prompt: str) -> LoopAdmission:
        """Conversation gate. Never raises; any failure is a fallback admission."""
        thread_id = configurable.get("thread_id")
        source = SourceKey(CONVERSATION, str(thread_id)) if thread_id else None
        admission = await self._judge(prompt, CONVERSATION)
        admission.source = source
        return admission

    async def extract(
        self,
        text: str,
        provenance: str,
        evidence: Sequence[EvidenceRef] = (),
        source_ref: str | None = None,
    ) -> None:
        """Email, calendar and ingestion inflows: judge, log, commit inline."""
        if not text or not text.strip():
            return
        source = SourceKey(provenance, source_ref) if source_ref else None
        admission = await self._judge(text, provenance)
        admission.source = source
        self._log(admission, provenance)
        if admission.commit is not None:
            await admission.commit(evidence)

    def _log(self, admission: LoopAdmission, provenance: str) -> None:
        judgment = admission.judgment
        answers = {
            qid: a.noul
            for qid, a in (judgment.answers.items() if judgment else ())
            if a.type == "noul"
        }
        log.info(
            "loop_gate_judgment",
            provenance=provenance,
            outcome=admission.decision.kind,
            reason=admission.decision.reason,
            consumed=sorted(admission.consumed),
            answers=answers,
            latency_ms=judgment.latency_ms if judgment else None,
            skip_reason=admission.skip_reason,
        )

    def _commit_for(self, text: str, provenance: str, admission: LoopAdmission):
        async def _commit(evidence: Sequence[EvidenceRef] = ()) -> list:
            try:
                return await propose_loop_candidates(
                    text=text,
                    provenance=provenance,
                    evidence_refs=list(evidence),
                    llm_client=self._llm,
                    embedder=self._embedder,
                    loop_store=self._loop_store,
                    entity_resolver=self._entity_resolver,
                    graph_store=self._graph_store,
                    memory_store=self._memory_store,
                    model=self._model,
                    collision_store=self._collision_store,
                    nli_client=self._nli_client,
                    admission=admission,
                    source=admission.source,
                    system_one_client=self._system_one,
                    settings=self._settings,
                )
            except Exception as exc:
                log.warning(
                    "loop_extraction_failed", provenance=provenance, error=str(exc)
                )
                return []

        return _commit

    def _finish(
        self,
        text: str,
        provenance: str,
        decision: LoopGateDecision,
        *,
        judgment: Any = None,
        question_ids: tuple[str, ...] = (),
        skip_reason: str | None = None,
    ) -> LoopAdmission:
        admission = LoopAdmission(
            decision=decision,
            judgment=judgment,
            question_ids=question_ids,
            question_kinds={
                qid: loop_judge.LOOP_QUESTIONS[qid].type for qid in question_ids
            },
            consumed=decision.consumed,
            skip_reason=skip_reason,
        )
        if decision.kind != "hold":
            admission.commit = self._commit_for(text, provenance, admission)
        return admission

    async def _judge(self, text: str, provenance: str) -> LoopAdmission:
        if (
            not text
            or not text.strip()
            or (provenance == CONVERSATION and is_trivial_turn(text))
        ):
            return self._finish(text, provenance, LoopGateDecision("hold", "trivial"))

        cfg = loop_gate_surface_config(self._settings)
        if not cfg.enabled:
            return self._finish(
                text, provenance, LoopGateDecision("fallback", "disabled")
            )
        if not cfg.calibrated:
            log.warning("loop_gate_uncalibrated")
            return self._finish(
                text,
                provenance,
                LoopGateDecision("fallback", "uncalibrated"),
                skip_reason="uncalibrated",
            )
        if self._system_one is None or not loop_judge.supported_provenance(provenance):
            return self._finish(
                text, provenance, LoopGateDecision("fallback", "unavailable")
            )

        questions = loop_judge.questions_for(provenance)
        try:
            result = await self._system_one.evaluate(
                loop_judge.build_state(text, provenance), questions, max_attempts=1
            )
        except Exception as exc:
            log.warning("loop_gate_system_one_call_failed", error=str(exc))
            return self._finish(
                text,
                provenance,
                LoopGateDecision("fallback", "error"),
                skip_reason="error",
            )
        decision = loop_judge.decide(result, cfg, provenance)
        if decision.reason == "invalid_answer":
            log.warning("loop_gate_invalid_answer")
        return self._finish(
            text,
            provenance,
            decision,
            judgment=result,
            question_ids=tuple(questions),
            skip_reason=decision.reason if decision.kind == "fallback" else None,
        )
