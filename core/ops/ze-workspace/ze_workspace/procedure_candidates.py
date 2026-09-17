from ze_agents.claims import Provenance
from ze_plugin.contribution import EvidenceRef

from ze_memory.procedures.types import ProcedureCandidate, ProcedureSourceKind
from ze_workspace.types import (
    WorkspaceRun,
    WorkspaceRunOrigin,
    WorkspaceRunStatus,
)


def workspace_run_is_approved(run: WorkspaceRun) -> bool:
    if run.status is not WorkspaceRunStatus.SUCCEEDED:
        return False
    return run.origin in {
        WorkspaceRunOrigin.USER,
        WorkspaceRunOrigin.UNATTENDED,
        WorkspaceRunOrigin.CONVERSATION,
    }


def candidate_from_workspace_run(run: WorkspaceRun) -> ProcedureCandidate:
    approved = workspace_run_is_approved(run)
    run_id = run.id
    evidence = [EvidenceRef(kind="goal", id=run_id)] if run_id else []
    command = run.command.strip() or "workspace command"
    return ProcedureCandidate(
        source_kind=ProcedureSourceKind.WORKSPACE_RUN,
        provenance=Provenance.SYNTHESIZED,
        name=command[:200],
        trigger="repeat an approved workspace command",
        preconditions=["the workspace is available"],
        steps=[command],
        success_criteria=["command exits 0"],
        evidence_refs=evidence,
        workspace_run_approved=approved,
    )
