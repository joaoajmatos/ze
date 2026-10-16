from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID as UUIDType

from pydantic import (
    BaseModel,
)


class ProcedureEvidenceRefResponse(BaseModel):
    kind: str
    id: UUIDType


class ProcedureCandidateResponse(BaseModel):
    id: UUIDType
    source_kind: str
    provenance: str
    name: str
    trigger: str
    preconditions: list[str]
    steps: list[str]
    success_criteria: list[str]
    limits: list[str]
    evidence_refs: list[ProcedureEvidenceRefResponse]
    learning_refs: list[UUIDType]
    status: str
    submitted_at: datetime | None
    resolved_at: datetime | None


class ProcedureVersionResponse(BaseModel):
    id: UUIDType
    procedure_id: UUIDType
    version_number: int
    name: str
    trigger: str
    preconditions: list[str]
    steps: list[str]
    success_criteria: list[str]
    limits: list[str]
    provenance: str
    status: str
    evidence_refs: list[ProcedureEvidenceRefResponse]
    learning_refs: list[UUIDType]


class ProcedureReviewRequest(BaseModel):
    decision: Literal["approve", "reject", "needs_review", "withdraw"]
    reason: str


class ProcedureDisableRequest(BaseModel):
    reason: str = "disabled by user"


class ProcedureEditRequest(BaseModel):
    name: str
    trigger: str
    preconditions: list[str] = []
    steps: list[str]
    success_criteria: list[str]
    limits: list[str] = []
    reason: str = "edited by user"


class ProcedureLifecycleEventResponse(BaseModel):
    kind: str
    reason: str
    version_id: UUIDType | None = None


class ProcedureFeedbackResponse(BaseModel):
    outcome: str
    summary: str
    procedure_version_id: UUIDType


class ProcedureSummaryResponse(BaseModel):
    id: UUIDType
    name: str
    identity_status: str
    version_status: str
    version_number: int
    trigger: str
    current_version_id: UUIDType | None = None
    evidence_refs: list[ProcedureEvidenceRefResponse]


class ProcedureDetailResponse(BaseModel):
    id: UUIDType
    name: str
    identity_status: str
    current_version_id: UUIDType | None = None
    versions: list[ProcedureVersionResponse]
    events: list[ProcedureLifecycleEventResponse]
    outcomes: list[ProcedureFeedbackResponse]


class ProcedureAdmissionResultResponse(BaseModel):
    candidate: ProcedureCandidateResponse
    version: ProcedureVersionResponse | None = None
