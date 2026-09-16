from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from ze_api.api.dependencies import get_procedure_admission, require_api_key
from ze_api.api.schemas import (
    ProcedureAdmissionResultResponse,
    ProcedureCandidateResponse,
    ProcedureDetailResponse,
    ProcedureDisableRequest,
    ProcedureEditRequest,
    ProcedureEvidenceRefResponse,
    ProcedureFeedbackResponse,
    ProcedureLifecycleEventResponse,
    ProcedureReviewRequest,
    ProcedureSummaryResponse,
    ProcedureVersionResponse,
)
from ze_memory.procedures.errors import (
    InvalidProcedureTransitionError,
    ProcedureLifecycleError,
)
from ze_memory.procedures.types import CandidateStatus, ProcedureAdmissionDecision

router = APIRouter(tags=["procedures"], dependencies=[Depends(require_api_key)])


def _evidence(refs) -> list[ProcedureEvidenceRefResponse]:
    return [ProcedureEvidenceRefResponse(kind=ref.kind, id=ref.id) for ref in refs]


def _candidate_response(candidate) -> ProcedureCandidateResponse:
    if candidate.id is None:
        raise HTTPException(status_code=500, detail="candidate missing id")
    return ProcedureCandidateResponse(
        id=candidate.id,
        source_kind=candidate.source_kind.value,
        provenance=candidate.provenance.value,
        name=candidate.name,
        trigger=candidate.trigger,
        preconditions=list(candidate.preconditions),
        steps=list(candidate.steps),
        success_criteria=list(candidate.success_criteria),
        limits=list(candidate.limits),
        evidence_refs=_evidence(candidate.evidence_refs),
        learning_refs=[ref.learning_id for ref in candidate.learning_refs],
        status=candidate.status.value,
        submitted_at=candidate.submitted_at,
        resolved_at=candidate.resolved_at,
    )


def _version_response(version) -> ProcedureVersionResponse:
    if version.id is None:
        raise HTTPException(status_code=500, detail="version missing id")
    return ProcedureVersionResponse(
        id=version.id,
        procedure_id=version.procedure_id,
        version_number=version.version_number,
        name=version.name,
        trigger=version.trigger,
        preconditions=list(version.preconditions),
        steps=list(version.steps),
        success_criteria=list(version.success_criteria),
        limits=list(version.limits),
        provenance=version.provenance.value,
        status=version.status.value,
        evidence_refs=_evidence(version.evidence_refs),
        learning_refs=[ref.learning_id for ref in version.learning_refs],
    )


@router.get(
    "/procedures/candidates",
    response_model=list[ProcedureCandidateResponse],
    operation_id="listProcedureCandidates",
    summary="List procedure candidates",
    description="Pending and needs-review procedure candidates awaiting admission.",
)
async def list_procedure_candidates(
    status: str | None = Query(default=None),
    procedures=Depends(get_procedure_admission),
) -> list[ProcedureCandidateResponse]:
    if procedures is None:
        return []
    statuses = None
    if status:
        statuses = [CandidateStatus(status)]
    else:
        statuses = [CandidateStatus.PENDING, CandidateStatus.NEEDS_REVIEW]
    rows = await procedures.list_procedure_candidates(statuses)
    return [_candidate_response(row) for row in rows]


@router.get(
    "/procedures",
    response_model=list[ProcedureVersionResponse],
    operation_id="listActiveProcedures",
    summary="List active procedures",
    description="Admitted active procedure versions only.",
)
async def list_active_procedures(
    procedures=Depends(get_procedure_admission),
) -> list[ProcedureVersionResponse]:
    if procedures is None:
        return []
    rows = await procedures.retrieve_procedures()
    return [_version_response(row) for row in rows]


@router.get(
    "/procedures/library",
    response_model=list[ProcedureSummaryResponse],
    operation_id="listProcedureLibrary",
    summary="List procedure identities",
    description="Current identity status and latest version for every procedure, including retired.",
)
async def list_procedure_library(
    procedures=Depends(get_procedure_admission),
) -> list[ProcedureSummaryResponse]:
    if procedures is None:
        return []
    rows = await procedures.list_procedure_summaries()
    result: list[ProcedureSummaryResponse] = []
    for identity, version in rows:
        if identity.id is None or version.id is None:
            continue
        result.append(
            ProcedureSummaryResponse(
                id=identity.id,
                name=identity.canonical_name or version.name,
                identity_status=identity.status.value,
                version_status=version.status.value,
                version_number=version.version_number,
                trigger=version.trigger,
                current_version_id=identity.active_version_id,
                evidence_refs=_evidence(version.evidence_refs),
            )
        )
    return result


@router.get(
    "/procedures/{procedure_id}",
    response_model=ProcedureDetailResponse,
    operation_id="getProcedure",
    summary="Get procedure detail",
    description="Identity, versions, evidence, lifecycle events, and outcome feedback.",
)
async def get_procedure(
    procedure_id: UUID,
    procedures=Depends(get_procedure_admission),
) -> ProcedureDetailResponse:
    if procedures is None:
        raise HTTPException(status_code=503, detail="Procedure admission unavailable")
    history = await procedures.lifecycle_history(procedure_id)
    identity = history["identity"]
    if identity is None or identity.id is None:
        raise HTTPException(status_code=404, detail="procedure not found")
    versions = history["versions"]
    outcomes = []
    for version in versions:
        if version.id is None:
            continue
        for item in await procedures.list_version_feedback(version.id):
            outcomes.append(
                ProcedureFeedbackResponse(
                    outcome=item.outcome.value,
                    summary=item.summary,
                    procedure_version_id=item.procedure_version_id,
                )
            )
    return ProcedureDetailResponse(
        id=identity.id,
        name=identity.canonical_name,
        identity_status=identity.status.value,
        current_version_id=identity.active_version_id,
        versions=[_version_response(row) for row in versions if row.id is not None],
        events=[
            ProcedureLifecycleEventResponse(
                kind=event.kind.value,
                reason=event.reason,
                version_id=event.version_id,
            )
            for event in history["events"]
        ],
        outcomes=outcomes,
    )


@router.post(
    "/procedures/{procedure_id}/edit",
    response_model=ProcedureAdmissionResultResponse,
    operation_id="editProcedure",
    summary="Edit a procedure",
    description="Submit a user-authored revision through the governed admission door.",
)
async def edit_procedure(
    procedure_id: UUID,
    body: ProcedureEditRequest,
    procedures=Depends(get_procedure_admission),
) -> ProcedureAdmissionResultResponse:
    if procedures is None:
        raise HTTPException(status_code=503, detail="Procedure admission unavailable")
    try:
        result = await procedures.edit_procedure(
            procedure_id,
            name=body.name,
            trigger=body.trigger,
            preconditions=body.preconditions,
            steps=body.steps,
            success_criteria=body.success_criteria,
            limits=body.limits,
            reason=body.reason,
        )
    except InvalidProcedureTransitionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ProcedureLifecycleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ProcedureAdmissionResultResponse(
        candidate=_candidate_response(result.candidate),
        version=_version_response(result.version) if result.version else None,
    )


@router.post(
    "/procedures/candidates/{candidate_id}/review",
    response_model=ProcedureAdmissionResultResponse,
    operation_id="reviewProcedureCandidate",
    summary="Review a procedure candidate",
    description="Approve, reject, hold, or withdraw a procedure candidate.",
)
async def review_procedure_candidate(
    candidate_id: UUID,
    body: ProcedureReviewRequest,
    procedures=Depends(get_procedure_admission),
) -> ProcedureAdmissionResultResponse:
    if procedures is None:
        raise HTTPException(status_code=503, detail="Procedure admission unavailable")
    try:
        result = await procedures.review_procedure_candidate(
            candidate_id,
            ProcedureAdmissionDecision(body.decision),
            reason=body.reason,
        )
    except InvalidProcedureTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ProcedureLifecycleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ProcedureAdmissionResultResponse(
        candidate=_candidate_response(result.candidate),
        version=_version_response(result.version) if result.version else None,
    )


@router.post(
    "/procedures/{procedure_id}/disable",
    response_model=ProcedureVersionResponse,
    operation_id="disableProcedure",
    summary="Disable a procedure",
    description="Immediately retire the procedure identity so it cannot match as ready.",
)
async def disable_procedure(
    procedure_id: UUID,
    body: ProcedureDisableRequest,
    procedures=Depends(get_procedure_admission),
) -> ProcedureVersionResponse:
    if procedures is None:
        raise HTTPException(status_code=503, detail="Procedure admission unavailable")
    try:
        await procedures.disable_procedure(procedure_id, reason=body.reason)
    except InvalidProcedureTransitionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    versions = await procedures.list_procedure_versions(procedure_id)
    latest = versions[-1] if versions else None
    if latest is None:
        raise HTTPException(status_code=404, detail="procedure version not found")
    return _version_response(latest)
