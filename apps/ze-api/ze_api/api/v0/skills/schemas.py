from __future__ import annotations

from typing import Any, Literal
from uuid import UUID as UUIDType

from pydantic import (
    BaseModel,
)


class SkillResponse(BaseModel):
    id: UUIDType
    name: str
    slug: str
    description: str
    source: Literal["bundled", "imported"]
    origin_url: str | None
    bundling_plugin: str | None
    status: Literal["pending_review", "active", "disabled", "rejected"]
    has_scripts: bool
    executable_approved: bool = False
    script_filenames: list[str] = []
    created_at: str | None
    approved_at: str | None
    last_checked_at: str | None
    last_check_error: str | None


class SkillListResponse(BaseModel):
    skills: list[SkillResponse]


class SkillReferenceFileSummary(BaseModel):
    filename: str
    content_type: str


class SkillDetailResponse(SkillResponse):
    instructions: str
    allowed_tools: list[str] | None
    reference_files: list[SkillReferenceFileSummary]
    previous_version: dict[str, Any] | None = None


class SkillImportRequest(BaseModel):
    url: str
