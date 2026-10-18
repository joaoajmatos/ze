from __future__ import annotations

from ze_memory.procedures.errors import (
    IncompleteProcedureCandidateError,
    InvalidProcedureEvidenceError,
    UnapprovedWorkspaceRunError,
)
from ze_memory.procedures.types import ProcedureCandidate, ProcedureSourceKind


TOOL_SCRIPT_MAX_CHARS = 8000


def validate_candidate(candidate: ProcedureCandidate) -> None:
    if not candidate.name.strip():
        raise IncompleteProcedureCandidateError("procedure name is required")
    if not candidate.trigger.strip():
        raise IncompleteProcedureCandidateError("procedure trigger is required")
    if not candidate.steps:
        raise IncompleteProcedureCandidateError("procedure steps are required")
    if not candidate.success_criteria:
        raise IncompleteProcedureCandidateError("success criteria are required")
    if candidate.source_kind is ProcedureSourceKind.WORKSPACE_RUN:
        if not candidate.workspace_run_approved:
            raise UnapprovedWorkspaceRunError(
                "workspace_run candidates require an approved run"
            )
        if not candidate.evidence_refs:
            raise InvalidProcedureEvidenceError(
                "workspace_run candidates require evidence references"
            )
    if candidate.source_kind is ProcedureSourceKind.REFLECTION:
        if not candidate.evidence_refs:
            raise InvalidProcedureEvidenceError(
                "reflection candidates require reviewer evidence"
            )
    if candidate.source_kind is ProcedureSourceKind.ACTION_PATTERN:
        if not candidate.evidence_refs:
            raise InvalidProcedureEvidenceError(
                "action_pattern candidates require supporting ActionRecord evidence"
            )
    if candidate.source_kind is ProcedureSourceKind.TOOL_SCRIPT:
        if not candidate.evidence_refs:
            raise InvalidProcedureEvidenceError(
                "tool_script candidates require ActionRecord evidence"
            )
        if len(candidate.steps) != 1:
            raise IncompleteProcedureCandidateError(
                "tool_script candidates take exactly one step (the script source)"
            )
        if len(candidate.steps[0]) > TOOL_SCRIPT_MAX_CHARS:
            raise IncompleteProcedureCandidateError(
                f"tool_script source is over {TOOL_SCRIPT_MAX_CHARS} characters"
            )
