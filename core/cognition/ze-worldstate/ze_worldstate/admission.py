"""Loop gate — one System One request per qualifying text, then a code-owned commit.

`LoopInflow` judges a text (email, calendar, ingestion) with the loop Nouls, decides in pure code,
and commits inline. The conversation inflow is judged by `CommitmentIntake` (173), which builds its
`LoopAdmission` through `finish`; this class never judges a conversation turn. Any failure falls back to the 109 Haiku gate (FR-012, FR-013).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ze_agents.client import LLMClient
from ze_agents.judgment import Judgment, gate, judge
from ze_logging import get_logger
from ze_plugin.contribution import EvidenceRef

from ze_worldstate import loop_judge
from ze_worldstate.extraction import DEFAULT_EXTRACTION_MODEL, propose_loop_candidates
from ze_worldstate.loop_judge import (
    LoopGateDecision,
    LoopGateSurfaceConfig,
    read_decision,
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
        decision = admission.decision
        answers = {
            qid: a.noul
            for qid, a in (judgment.result.answers.items() if judgment else ())
            if a.type == "noul"
        }
        if judgment is not None:
            consumed, skip_reason = judgment.consumed, judgment.skip_reason
        else:
            consumed = decision.consumed
            skip_reason = decision.reason if decision.kind == "fallback" else None
        log.info(
            "loop_gate_judgment",
            provenance=provenance,
            outcome=decision.kind,
            reason=decision.reason,
            consumed=sorted(consumed),
            answers=answers,
            latency_ms=judgment.result.latency_ms if judgment else None,
            skip_reason=skip_reason,
        )

    def commit_for(self, text: str, provenance: str, admission: LoopAdmission):
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

    def finish(
        self,
        text: str,
        provenance: str,
        decision: LoopGateDecision,
        *,
        judgment: Judgment | None = None,
    ) -> LoopAdmission:
        admission = LoopAdmission(decision=decision, judgment=judgment)
        if decision.kind != "hold":
            admission.commit = self.commit_for(text, provenance, admission)
        return admission

    async def _judge(self, text: str, provenance: str) -> LoopAdmission:
        if not text or not text.strip():
            return self.finish(text, provenance, LoopGateDecision("hold", "trivial"))

        cfg = LoopGateSurfaceConfig.from_settings(self._settings)
        reason = gate(cfg, self._system_one)
        if reason is None and not loop_judge.supported_provenance(provenance):
            reason = "unavailable"
        if reason is not None:
            return self.finish(
                text, provenance, LoopGateDecision("fallback", reason)
            )

        judgment, decision = await judge(
            self._system_one,
            cfg,
            loop_judge.build_state(text, provenance),
            loop_judge.LOOP_QUESTIONS,
            lambda result: loop_judge.decide(result, cfg, provenance),
            read_decision,
        )
        if decision.reason == "invalid_answer":
            log.warning("loop_gate_invalid_answer")
        return self.finish(text, provenance, decision, judgment=judgment)
