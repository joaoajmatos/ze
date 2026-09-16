from __future__ import annotations

from ze_agents.claims import Provenance
from ze_memory.procedures.types import (
    LearningRef,
    ProcedureCandidate,
    ProcedureSourceKind,
)
from ze_memory.types import Procedure
from ze_plugin.contribution import EvidenceRef
from uuid import UUID


def candidate_from_procedure(
    procedure: Procedure,
    *,
    source_kind: ProcedureSourceKind,
    provenance: Provenance,
    evidence_refs: list[EvidenceRef],
    learning_refs: list[LearningRef] | None = None,
    workspace_run_approved: bool = False,
    proposed_identity_id: UUID | None = None,
) -> ProcedureCandidate:
    return ProcedureCandidate(
        source_kind=source_kind,
        provenance=provenance,
        name=procedure.name,
        trigger=procedure.trigger,
        preconditions=list(procedure.preconditions),
        steps=list(procedure.steps),
        success_criteria=list(procedure.success_criteria),
        evidence_refs=evidence_refs,
        learning_refs=list(learning_refs or []),
        workspace_run_approved=workspace_run_approved,
        proposed_identity_id=proposed_identity_id,
    )


def candidate_from_action_pattern(
    *,
    name: str,
    trigger: str,
    steps: list[str],
    success_criteria: list[str],
    action_record_ids: list[UUID],
    outcomes: list[str],
    preconditions: list[str] | None = None,
    provenance: Provenance = Provenance.SYNTHESIZED,
) -> ProcedureCandidate | None:
    if any(outcome == "failed" for outcome in outcomes):
        return None
    if len(action_record_ids) < 2:
        return None
    return ProcedureCandidate(
        source_kind=ProcedureSourceKind.ACTION_PATTERN,
        provenance=provenance,
        name=name,
        trigger=trigger,
        preconditions=list(preconditions or []),
        steps=steps,
        success_criteria=success_criteria,
        evidence_refs=[
            EvidenceRef(kind="action_record", id=record_id)
            for record_id in action_record_ids
        ],
    )
