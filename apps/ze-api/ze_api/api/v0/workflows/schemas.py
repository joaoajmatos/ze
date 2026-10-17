from __future__ import annotations

from typing import Literal
from uuid import UUID as UUIDType

from pydantic import (
    BaseModel,
)


class BranchResponse(BaseModel):
    condition: str
    to: str


class StepResultResponse(BaseModel):
    step_index: int
    task: str
    output: str
    success: bool
    error: str | None
    duration_ms: int
    step_id: str
    branch_taken: str | None
    attempt_count: int = 1
    no_results: bool = False


class WorkflowStepResponse(BaseModel):
    task: str
    agent_hint: str | None
    verify: str | None
    id: str
    branches: list[BranchResponse]
    default_next: str | None
    on_failure: str = "fail"
    planned_writes: list[str] = []
    approved_writes: list[str] = []


class WorkflowResponse(BaseModel):
    id: UUIDType
    name: str
    description: str
    schedule: str | None
    enabled: bool
    last_run_at: str | None
    next_run_at: str | None
    created_at: str


class WorkflowDetailResponse(WorkflowResponse):
    steps: list[WorkflowStepResponse]


class WorkflowExecutionResponse(BaseModel):
    id: UUIDType
    workflow_id: UUIDType | None
    status: str
    step_results: list[StepResultResponse]
    steps_snapshot: list[WorkflowStepResponse] = []
    error: str | None
    failure_summary: str | None
    summary: str | None
    started_at: str | None
    completed_at: str | None
    created_at: str


class TriggerWorkflowResponse(BaseModel):
    status: str
    workflow_id: UUIDType
    execution_id: UUIDType


class CancelWorkflowExecutionResponse(BaseModel):
    status: Literal["cancelled", "not_running"]
    execution_id: UUIDType
    message: str


class WorkflowRevisionResponse(BaseModel):
    id: UUIDType
    workflow_id: UUIDType
    revision_number: int
    change_type: Literal["created", "edited"]
    steps_before: list[WorkflowStepResponse]
    steps_after: list[WorkflowStepResponse]
    summary: str
    actor_source: Literal["agent", "api", "system"]
    actor_session_id: str | None = None
    actor_user_message_id: str | None = None
    created_at: str
