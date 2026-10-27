"""Loop gate — one System One request per qualifying text, then a code-owned commit.

`LoopInflow` judges a text (email, calendar, ingestion) with the loop Nouls, decides in pure code,
and commits inline. The conversation inflow is judged by `CommitmentIntake` (173), which builds its
`LoopAdmission` through `finish`; this class never judges a conversation turn. Any failure falls back to the 109 Haiku gate (FR-012, FR-013).
`commit` is the one path from a `CommitDecision` to the lifecycle; it never raises.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any
from uuid import UUID

from ze_agents.client import LLMClient
from ze_logging import get_logger
from ze_plugin.contribution import EvidenceRef

from ze_worldstate import loop_judge
from ze_worldstate.corroboration import Corroborator, MatchInput
from ze_worldstate.decision import CommitDecision, CommitResult
from ze_worldstate.extraction import (
    DEFAULT_EXTRACTION_MODEL,
    decide_with_109_gate,
    resolve_entities,
    write_loop_title,
)
from ze_worldstate.fingerprint import compute_evidence_fingerprint
from ze_worldstate.lifecycle import LoopDraft, SourceWrite
from ze_worldstate.loop_judge import loop_gate_surface_config
from ze_worldstate.matching import find_matching_loop
from ze_worldstate.types import (
    LoopAdmission,
    LoopProvenance,
    LoopState,
    OpenLoop,
    SourceKey,
    TitleWriterResult,
)

__all__ = ["LoopAdmission", "LoopInflow", "TitleWriterResult"]

log = get_logger(__name__)

_LIVE = ["suspected", "active", "drifting"]


@dataclass(frozen=True)
class _Commit:
    """What one commit knows: the text, where it came from, and what the decision resolved to."""

    decision: CommitDecision
    text: str
    inflow: str
    evidence: tuple[EvidenceRef, ...]
    source: SourceKey | None
    title: str = ""
    window_days: int | None = None
    entity_ids: tuple[UUID, ...] = ()


class LoopInflow:
    def __init__(
        self,
        *,
        lifecycle: Any,
        loop_store: Any,
        graph_store: Any,
        entity_resolver: Any,
        llm_client: LLMClient,
        embedder: Any,
        system_one_client: Any = None,
        settings: Any = None,
        model: str = DEFAULT_EXTRACTION_MODEL,
    ) -> None:
        self._lifecycle = lifecycle
        self._loop_store = loop_store
        self._graph_store = graph_store
        self._entity_resolver = entity_resolver
        self._llm = llm_client
        self._embedder = embedder
        self._system_one = system_one_client
        self._settings = settings
        self._model = model
        self._corroborator = Corroborator(
            lifecycle=lifecycle,
            loop_store=loop_store,
            system_one_client=system_one_client,
            settings=settings,
        )

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
        self._log(admission, provenance)
        await self.commit(
            admission.decision,
            text=text,
            inflow=provenance,
            evidence=evidence,
            source=source,
        )

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

    async def commit(
        self,
        decision: CommitDecision,
        *,
        text: str,
        inflow: str,
        evidence: Sequence[EvidenceRef] = (),
        source: SourceKey | None = None,
    ) -> CommitResult:
        """The one commit path from a decision to the lifecycle. Never raises."""
        try:
            return await self._commit(
                _Commit(decision, text, inflow, tuple(evidence), source)
            )
        except Exception as exc:
            log.warning("loop_commit_failed", inflow=inflow, error=str(exc))
            return CommitResult("error", str(exc) or type(exc).__name__)

    async def _commit(self, c: _Commit) -> CommitResult:
        decision = c.decision
        if decision.kind == "fallback":
            decision = await decide_with_109_gate(c.text, self._llm, self._model)
        if decision.kind == "hold":
            return CommitResult("held", decision.reason)
        title, window = decision.title, decision.window_days
        if title is None:
            written = await self._write_title(c, decision.kind)
            if written is None:
                return CommitResult("no_title", decision.reason)
            title, window = written.title, written.implied_window_days
        entity_ids = tuple(await resolve_entities(self._entity_resolver, c.text))
        c = replace(
            c, decision=decision, title=title, window_days=window, entity_ids=entity_ids
        )
        if decision.kind == "resolve":
            return await self._resolve(c)
        if decision.kind == "create_suspected":
            return await self._create_suspected(c)
        return await self._create_declared(c)

    async def _write_title(self, c: _Commit, kind: str) -> TitleWriterResult | None:
        text = (
            loop_judge.capped_text(c.text, c.inflow)
            if loop_judge.supported_provenance(c.inflow)
            else c.text
        )
        return await write_loop_title(
            text, "resolve" if kind == "resolve" else "create", self._llm, self._model
        )

    async def _match(self, c: _Commit, states: list[str]) -> OpenLoop | None:
        if self._graph_store is None:
            return None
        return await find_matching_loop(
            list(c.entity_ids),
            c.title,
            loop_store=self._loop_store,
            graph_store=self._graph_store,
            embedder=self._embedder,
            states=states,
        )

    async def _resolve(self, c: _Commit) -> CommitResult:
        existing = await self._match(c, _LIVE)
        if existing is None or existing.id is None:
            return CommitResult("no_match", c.decision.reason)
        closed = await self._lifecycle.resolve(existing.id, evidence=c.evidence)
        if closed is None:
            return CommitResult("no_match", "not_live")
        return CommitResult("resolved", c.decision.reason, (closed,))

    async def _create_suspected(self, c: _Commit) -> CommitResult:
        dropped = await self._match(c, ["dropped"])
        if (
            dropped is not None
            and dropped.dismissed_evidence_fingerprint
            == compute_evidence_fingerprint(list(c.evidence))
        ):
            # FR-011: don't resurface a loop from evidence the user already dismissed.
            return CommitResult("dismissed", "dismissed_evidence")
        existing = await self._match(c, _LIVE)
        if existing is not None:
            return await self._on_match(c, existing, dropped)
        created = await self._lifecycle.create_suspected(self._draft(c, c.inflow))
        return CommitResult("created", c.decision.reason, (created,))

    async def _create_declared(self, c: _Commit) -> CommitResult:
        existing = await self._match(c, _LIVE)
        if existing is not None:
            dropped = (
                await self._match(c, ["dropped"])
                if existing.state is LoopState.SUSPECTED
                else None
            )
            return await self._on_match(c, existing, dropped)
        provenance = (
            LoopProvenance.USER_DECLARED
            if c.inflow == LoopProvenance.CONVERSATION
            else c.inflow
        )
        created = await self._lifecycle.create_declared(
            self._draft(c, provenance), window_days=c.window_days
        )
        return CommitResult("created", c.decision.reason, (created,))

    def _draft(self, c: _Commit, provenance: str) -> LoopDraft:
        return LoopDraft(c.title, provenance, c.evidence, c.entity_ids, source=c.source)

    async def _on_match(
        self, c: _Commit, existing: OpenLoop, dropped: OpenLoop | None
    ) -> CommitResult:
        if existing.id is None:
            return CommitResult("error", "match_without_id")
        if existing.state is not LoopState.SUSPECTED:
            loop = await self._lifecycle.note_evidence(
                existing.id, evidence=c.evidence, entity_ids=c.entity_ids
            )
        else:
            written = await self._corroborator.on_suspected_match(
                existing,
                dropped,
                MatchInput(
                    c.text,
                    c.source.inflow if c.source else c.inflow,
                    c.source,
                    c.evidence,
                    c.entity_ids,
                ),
            )
            loop = written.loop if isinstance(written, SourceWrite) else written
        return CommitResult("matched", c.decision.reason, (loop,))

    def finish(
        self,
        text: str,
        provenance: str,
        decision: CommitDecision,
        *,
        judgment: Any = None,
        question_ids: tuple[str, ...] = (),
        skip_reason: str | None = None,
        source: SourceKey | None = None,
    ) -> LoopAdmission:
        return LoopAdmission(
            decision=decision,
            judgment=judgment,
            question_ids=question_ids,
            question_kinds={
                qid: loop_judge.LOOP_QUESTIONS[qid].type for qid in question_ids
            },
            consumed=decision.consumed,
            skip_reason=skip_reason,
            source=source,
            text=text,
            inflow=provenance,
        )

    async def _judge(self, text: str, provenance: str) -> LoopAdmission:
        if not text or not text.strip():
            return self.finish(text, provenance, CommitDecision("hold", "trivial"))

        cfg = loop_gate_surface_config(self._settings)
        if not cfg.enabled:
            return self.finish(text, provenance, CommitDecision("fallback", "disabled"))
        if not cfg.calibrated:
            log.warning("loop_gate_uncalibrated")
            return self.finish(
                text,
                provenance,
                CommitDecision("fallback", "uncalibrated"),
                skip_reason="uncalibrated",
            )
        if self._system_one is None or not loop_judge.supported_provenance(provenance):
            return self.finish(
                text, provenance, CommitDecision("fallback", "unavailable")
            )

        questions = dict(loop_judge.LOOP_QUESTIONS)
        try:
            result = await self._system_one.evaluate(
                loop_judge.build_state(text, provenance), questions, max_attempts=1
            )
        except Exception as exc:
            log.warning("loop_gate_system_one_call_failed", error=str(exc))
            return self.finish(
                text,
                provenance,
                CommitDecision("fallback", "error"),
                skip_reason="error",
            )
        decision = loop_judge.decide(result, cfg, provenance)
        if decision.reason == "invalid_answer":
            log.warning("loop_gate_invalid_answer")
        return self.finish(
            text,
            provenance,
            decision,
            judgment=result,
            question_ids=tuple(questions),
            skip_reason=decision.reason if decision.kind == "fallback" else None,
        )
