from __future__ import annotations

from ze_agents.claims import Provenance
from ze_plugin.contribution import EvidenceRef

from ze_memory.procedures.types import ProcedureCandidate, ProcedureSourceKind
from ze_workspace.types import (
    WorkspaceMode,
    WorkspaceRun,
    WorkspaceRunOrigin,
    WorkspaceRunStatus,
)


def workspace_run_is_approved(run: WorkspaceRun, mode: WorkspaceMode) -> bool:
    if run.status is not WorkspaceRunStatus.SUCCEEDED:
        return False
    if run.origin is WorkspaceRunOrigin.USER:
        return True
    if run.origin is WorkspaceRunOrigin.UNATTENDED and mode is WorkspaceMode.AUTO:
        return True
    return False


def candidate_from_workspace_run(
    run: WorkspaceRun, *, mode: WorkspaceMode
) -> ProcedureCandidate:
    approved = workspace_run_is_approved(run, mode)
    run_id = run.id
    evidence = [EvidenceRef(kind="goal", id=run_id)] if run_id else []
    command = run.command.strip() or "workspace command"
    return ProcedureCandidate(
        source_kind=ProcedureSourceKind.WORKSPACE_RUN,
        provenance=Provenance.SYNTHESIZED,
        name=command[:200],
        trigger="repeat an approved workspace command",
        preconditions=["workspace mode allows the original command"],
        steps=[command],
        success_criteria=["command exits 0"],
        evidence_refs=evidence,
        workspace_run_approved=approved,
    )
