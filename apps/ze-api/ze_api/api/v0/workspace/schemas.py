from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
)

WorkspaceRunOriginLiteral = Literal["conversation", "user", "unattended"]


WorkspaceRunStatusLiteral = Literal[
    "succeeded", "failed", "timed_out", "cancelled", "refused", "in_progress"
]


class WorkspaceStatusResponse(BaseModel):
    available: bool
    bytes_used: int
    bytes_ceiling: int
    busy: bool
    last_reset_at: str | None
    last_used_at: str | None


class WorkspaceFileItem(BaseModel):
    path: str
    size: int
    modified_at: str
    is_dir: bool


class WorkspaceFileListResponse(BaseModel):
    files: list[WorkspaceFileItem]


class WorkspaceUploadResponse(BaseModel):
    path: str
    requested_path: str
    size: int
    deduplicated: bool


class WorkspaceFileTouchResponse(BaseModel):
    path: str
    op: str


class WorkspaceRunResponse(BaseModel):
    id: str | None
    started_at: str | None
    ended_at: str | None
    command: str
    origin: WorkspaceRunOriginLiteral
    thread_id: str | None
    message_id: str | None
    skill_id: str | None
    skill_script_path: str | None
    status: WorkspaceRunStatusLiteral
    exit_code: int | None
    output_preview: str
    output_file_path: str | None
    files_touched: list[WorkspaceFileTouchResponse]
    error_summary: str | None
    follow_through_notified: bool = False


class WorkspaceRunListResponse(BaseModel):
    runs: list[WorkspaceRunResponse]
