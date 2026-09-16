from __future__ import annotations

from uuid import uuid4

import pytest
from ze_agents.claims import Provenance
from ze_plugin.contribution import EvidenceRef

from ze_memory.procedures.admission import ProcedureAdmissionService
from ze_memory.procedures.errors import InvalidProcedureTransitionError
from ze_memory.procedures.store import InMemoryProcedureStore
from ze_memory.procedures.types import (
    CandidateStatus,
    LearningRef,
    ProcedureAdmissionDecision,
    ProcedureCandidate,
    ProcedureSourceKind,
    VersionStatus,
)


def _candidate(**overrides) -> ProcedureCandidate:
    base = dict(
        source_kind=ProcedureSourceKind.GOAL,
        provenance=Provenance.SYNTHESIZED,
        name="Short feedback loops",
        trigger="planning a study session",
        preconditions=["goal exists"],
        steps=["review last session"],
        success_criteria=["session booked"],
        evidence_refs=[EvidenceRef(kind="goal", id=uuid4())],
        learning_refs=[LearningRef(learning_id=uuid4())],
    )
    base.update(overrides)
    return ProcedureCandidate(**base)


async def test_approve_creates_one_active_version() -> None:
    service = ProcedureAdmissionService(InMemoryProcedureStore())
    saved = await service.submit_procedure_candidate(_candidate())
    result = await service.review_procedure_candidate(
        saved.id,
        ProcedureAdmissionDecision.APPROVE,
        reason="complete playbook",
    )
    assert result.candidate.status is CandidateStatus.APPROVED
    assert result.version is not None
    assert result.version.status is VersionStatus.ACTIVE
    active = await service.retrieve_procedures()
    assert len(active) == 1


async def test_reject_creates_no_active_version() -> None:
    service = ProcedureAdmissionService(InMemoryProcedureStore())
    saved = await service.submit_procedure_candidate(_candidate())
    result = await service.review_procedure_candidate(
        saved.id,
        ProcedureAdmissionDecision.REJECT,
        reason="incomplete evidence",
    )
    assert result.version is None
    assert await service.retrieve_procedures() == []


async def test_needs_review_is_not_retrievable() -> None:
    service = ProcedureAdmissionService(InMemoryProcedureStore())
    saved = await service.submit_procedure_candidate(_candidate())
    await service.review_procedure_candidate(
        saved.id,
        ProcedureAdmissionDecision.NEEDS_REVIEW,
        reason="low confidence",
    )
    assert await service.retrieve_procedures() == []


async def test_second_approval_supersedes() -> None:
    service = ProcedureAdmissionService(InMemoryProcedureStore())
    first = await service.submit_procedure_candidate(_candidate())
    admitted = await service.review_procedure_candidate(
        first.id,
        ProcedureAdmissionDecision.APPROVE,
        reason="v1",
    )
    second = await service.submit_procedure_candidate(
        _candidate(
            proposed_identity_id=admitted.identity.id,
            steps=["review last session", "add buffer"],
        )
    )
    v2 = await service.review_procedure_candidate(
        second.id,
        ProcedureAdmissionDecision.APPROVE,
        reason="v2",
    )
    assert v2.version.version_number == 2
    active = await service.retrieve_procedures()
    assert len(active) == 1
    assert active[0].id == v2.version.id
    history = await service.retrieve_procedures(include_history=True)
    assert len(history) == 2


async def test_cannot_reapprove_terminal_candidate() -> None:
    service = ProcedureAdmissionService(InMemoryProcedureStore())
    saved = await service.submit_procedure_candidate(_candidate())
    await service.review_procedure_candidate(
        saved.id, ProcedureAdmissionDecision.REJECT, reason="no"
    )
    with pytest.raises(InvalidProcedureTransitionError):
        await service.review_procedure_candidate(
            saved.id, ProcedureAdmissionDecision.APPROVE, reason="too late"
        )
