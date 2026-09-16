from __future__ import annotations

from uuid import uuid4

from ze_agents.claims import Provenance
from ze_plugin.contribution import EvidenceRef

from ze_memory.procedures.admission import ProcedureAdmissionService
from ze_memory.procedures.store import InMemoryProcedureStore
from ze_memory.procedures.types import (
    ProcedureAdmissionDecision,
    ProcedureCandidate,
    ProcedureSourceKind,
    VersionStatus,
)


async def test_rollback_restores_prior_version() -> None:
    service = ProcedureAdmissionService(InMemoryProcedureStore())
    v1 = await service.submit_procedure_candidate(
        ProcedureCandidate(
            source_kind=ProcedureSourceKind.USER_INSTRUCTION,
            provenance=Provenance.PROMPT_SUPPLIED,
            name="Morning review",
            trigger="start of day",
            preconditions=[],
            steps=["open inbox"],
            success_criteria=["inbox triaged"],
            evidence_refs=[EvidenceRef(kind="goal", id=uuid4())],
        )
    )
    first = await service.review_procedure_candidate(
        v1.id, ProcedureAdmissionDecision.APPROVE, reason="v1"
    )
    v2 = await service.submit_procedure_candidate(
        ProcedureCandidate(
            source_kind=ProcedureSourceKind.USER_INSTRUCTION,
            provenance=Provenance.PROMPT_SUPPLIED,
            name="Morning review",
            trigger="start of day",
            preconditions=[],
            steps=["open inbox", "also rewrite all mail"],
            success_criteria=["inbox triaged"],
            proposed_identity_id=first.identity.id,
            evidence_refs=[EvidenceRef(kind="goal", id=uuid4())],
        )
    )
    second = await service.review_procedure_candidate(
        v2.id, ProcedureAdmissionDecision.APPROVE, reason="v2"
    )
    result = await service.rollback_procedure(
        first.identity.id,
        target_version_id=first.version.id,
        reason="v2 was harmful",
    )
    assert result.retired is False
    assert result.restored_version.id == first.version.id
    active = await service.retrieve_procedures()
    assert active[0].id == first.version.id
    loaded = await service._store.get_version(second.version.id)
    assert loaded.status is VersionStatus.ROLLED_BACK
