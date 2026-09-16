from __future__ import annotations

from uuid import uuid4

from ze_agents.claims import Provenance
from ze_plugin.contribution import EvidenceRef

from ze_memory.procedures.admission import ProcedureAdmissionService
from ze_memory.procedures.errors import MissingActionRecordError
from ze_memory.procedures.sources import candidate_from_action_pattern
from ze_memory.procedures.store import InMemoryProcedureStore
from ze_memory.procedures.types import (
    LearningRef,
    ProcedureAdmissionDecision,
    ProcedureCandidate,
    ProcedureOutcome,
    ProcedureSourceKind,
)


def _candidate() -> ProcedureCandidate:
    return ProcedureCandidate(
        source_kind=ProcedureSourceKind.ACTION_PATTERN,
        provenance=Provenance.SYNTHESIZED,
        name="Retry with backoff",
        trigger="outbound send failed",
        preconditions=["channel connected"],
        steps=["wait", "retry once"],
        success_criteria=["message sent"],
        evidence_refs=[EvidenceRef(kind="action_record", id=uuid4())],
    )


async def test_failed_pattern_is_not_auto_admitted() -> None:
    skipped = candidate_from_action_pattern(
        name="Retry with backoff",
        trigger="outbound send failed",
        steps=["wait", "retry once"],
        success_criteria=["message sent"],
        action_record_ids=[uuid4(), uuid4()],
        outcomes=["succeeded", "failed"],
    )
    assert skipped is None
    service = ProcedureAdmissionService(InMemoryProcedureStore())
    saved = await service.submit_procedure_candidate(_candidate())
    assert saved.status.value == "pending"
    assert await service.retrieve_procedures() == []


async def test_feedback_requires_existing_action_record() -> None:
    store = InMemoryProcedureStore()
    service = ProcedureAdmissionService(store)
    saved = await service.submit_procedure_candidate(_candidate())
    admitted = await service.review_procedure_candidate(
        saved.id, ProcedureAdmissionDecision.APPROVE, reason="ok"
    )
    try:
        await service.record_procedure_feedback(
            admitted.version.id,
            action_record_id=uuid4(),
            outcome=ProcedureOutcome.FAILED,
            summary="send failed",
            evidence=[],
            learnings=[LearningRef(learning_id=uuid4())],
        )
        raise AssertionError("missing action record must fail")
    except MissingActionRecordError:
        pass
    assert admitted.version.steps == ["wait", "retry once"]
