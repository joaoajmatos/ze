from __future__ import annotations

from uuid import uuid4

from ze_agents.claims import Provenance
from ze_plugin.contribution import EvidenceRef

from ze_memory.procedures.admission import ProcedureAdmissionService
from ze_memory.procedures.retrieval import project_procedure_history
from ze_memory.procedures.store import InMemoryProcedureStore
from ze_memory.procedures.types import (
    ProcedureAdmissionDecision,
    ProcedureCandidate,
    ProcedureSourceKind,
    VersionStatus,
)


async def test_default_retrieval_excludes_history() -> None:
    service = ProcedureAdmissionService(InMemoryProcedureStore())
    first = await service.submit_procedure_candidate(
        ProcedureCandidate(
            source_kind=ProcedureSourceKind.USER_INSTRUCTION,
            provenance=Provenance.PROMPT_SUPPLIED,
            name="Inbox sweep",
            trigger="morning",
            preconditions=[],
            steps=["open inbox"],
            success_criteria=["triaged"],
            evidence_refs=[EvidenceRef(kind="goal", id=uuid4())],
        )
    )
    admitted = await service.review_procedure_candidate(
        first.id, ProcedureAdmissionDecision.APPROVE, reason="v1"
    )
    second = await service.submit_procedure_candidate(
        ProcedureCandidate(
            source_kind=ProcedureSourceKind.USER_INSTRUCTION,
            provenance=Provenance.PROMPT_SUPPLIED,
            name="Inbox sweep",
            trigger="morning",
            preconditions=[],
            steps=["open inbox", "archive promo"],
            success_criteria=["triaged"],
            proposed_identity_id=admitted.identity.id,
            evidence_refs=[EvidenceRef(kind="goal", id=uuid4())],
        )
    )
    await service.review_procedure_candidate(
        second.id, ProcedureAdmissionDecision.APPROVE, reason="v2"
    )
    active = await service.retrieve_procedures()
    assert len(active) == 1
    history = await service.retrieve_procedures(include_history=True)
    assert len(history) == 2
    projected = await project_procedure_history(service, admitted.identity.id)
    assert projected["active"][0].status is VersionStatus.ACTIVE
    assert any(v.status is VersionStatus.SUPERSEDED for v in projected["inactive"])
