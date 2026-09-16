from __future__ import annotations

from uuid import uuid4

import pytest
from ze_agents.claims import Provenance
from ze_plugin.contribution import EvidenceRef

from ze_memory.procedures.errors import (
    IncompleteProcedureCandidateError,
    UnapprovedWorkspaceRunError,
)
from ze_memory.procedures.types import (
    LearningRef,
    ProcedureCandidate,
    ProcedureSourceKind,
)
from ze_memory.procedures.validate import validate_candidate


def _candidate(**overrides) -> ProcedureCandidate:
    base = dict(
        source_kind=ProcedureSourceKind.GOAL,
        provenance=Provenance.SYNTHESIZED,
        name="Short feedback loops",
        trigger="planning a study session",
        preconditions=["goal exists"],
        steps=["review last session", "schedule next block"],
        success_criteria=["next session is booked"],
        evidence_refs=[EvidenceRef(kind="goal", id=uuid4())],
        learning_refs=[LearningRef(learning_id=uuid4())],
    )
    base.update(overrides)
    return ProcedureCandidate(**base)


def test_complete_candidate_is_valid() -> None:
    validate_candidate(_candidate())


def test_missing_steps_rejected() -> None:
    with pytest.raises(IncompleteProcedureCandidateError):
        validate_candidate(_candidate(steps=[]))


def test_unapproved_workspace_run_rejected() -> None:
    with pytest.raises(UnapprovedWorkspaceRunError):
        validate_candidate(
            _candidate(
                source_kind=ProcedureSourceKind.WORKSPACE_RUN,
                workspace_run_approved=False,
            )
        )


def test_learning_refs_are_preserved() -> None:
    learning_id = uuid4()
    candidate = _candidate(learning_refs=[LearningRef(learning_id=learning_id)])
    assert candidate.learning_refs[0].learning_id == learning_id
