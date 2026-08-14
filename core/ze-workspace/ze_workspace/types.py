from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class WorkspaceMode(StrEnum):
    OFF = "off"
    PLAN = "plan"
    ASK = "ask"
    AUTO_EDIT = "auto_edit"
    AUTO = "auto"


class WorkspaceRunStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    REFUSED = "refused"


class WorkspaceRunOrigin(StrEnum):
    CONVERSATION = "conversation"
    USER = "user"
    UNATTENDED = "unattended"


class WorkspaceAction(StrEnum):
    LIST = "list"
    READ = "read"
    PLACE = "place"
    RETRIEVE = "retrieve"
    WRITE = "write"
    DELETE = "delete"
    RUN = "run"
    RUN_SCRIPT = "run_script"
    RESET = "reset"
    INGEST = "ingest"


class WorkspaceGateDecision(StrEnum):
    ALLOW = "allow"
    CONFIRM = "confirm"
    PLAN = "plan"
    DENY = "deny"


@dataclass
class WorkspaceFile:
    path: str
    size: int
    modified_at: datetime
    is_dir: bool = False


@dataclass
class WorkspaceFileTouch:
    path: str
    op: str  # "created" | "updated" | "deleted"


@dataclass
class WorkspaceRun:
    command: str
    origin: WorkspaceRunOrigin
    status: WorkspaceRunStatus
    id: UUID | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    thread_id: str | None = None
    message_id: UUID | None = None
    skill_id: UUID | None = None
    skill_script_path: str | None = None
    exit_code: int | None = None
    output_preview: str = ""
    output_file_path: str | None = None
    files_touched: list[WorkspaceFileTouch] = field(default_factory=list)
    error_summary: str | None = None


@dataclass
class WorkspaceState:
    mode: WorkspaceMode = WorkspaceMode.ASK
    last_reset_at: datetime | None = None
    last_used_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class WorkspaceStat:
    bytes_used: int
    bytes_ceiling: int
    busy: bool
    workspace_root: str = "/workspace"
    available: bool = True


@dataclass
class WorkspaceRunResult:
    exit_code: int
    timed_out: bool
    stdout_preview: str
    stderr_preview: str
    output_file_path: str | None = None
    files_touched: list[WorkspaceFileTouch] = field(default_factory=list)
