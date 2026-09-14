from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class SkillStatus(StrEnum):
    PENDING_REVIEW = "pending_review"
    ACTIVE = "active"
    DISABLED = "disabled"
    REJECTED = "rejected"


class SkillSource(StrEnum):
    BUNDLED = "bundled"
    IMPORTED = "imported"


class SkillTrigger(StrEnum):
    """Used only in `SkillUsageTrace`/`SkillMatch`, not stored on `Skill` itself."""

    AUTOMATIC = "automatic"
    EXPLICIT = "explicit"


_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    """Lowercase, hyphenated derivation of `name` — used for `/skill-name` invocation
    matching (FR-019b) and for distinguishing same-named skills by pairing with
    `source` (FR-017)."""
    slug = _SLUG_STRIP_RE.sub("-", name.strip().lower()).strip("-")
    return slug


def compute_content_hash(
    name: str,
    description: str,
    instructions: str,
    allowed_tools: list[str] | None,
) -> str:
    """Hash of the currently-approved `(name, description, instructions, allowed_tools)`
    tuple; compared on recheck (FR-015)."""
    payload = json.dumps(
        {
            "name": name,
            "description": description,
            "instructions": instructions,
            "allowed_tools": sorted(allowed_tools) if allowed_tools else None,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class ReferenceFile:
    filename: str
    content: str
    content_type: str
    skill_id: UUID | None = None
    id: UUID | None = None


@dataclass
class Skill:
    name: str
    description: str
    instructions: str
    source: SkillSource
    slug: str = ""
    origin_url: str | None = None
    bundling_plugin: str | None = None
    status: SkillStatus = SkillStatus.PENDING_REVIEW
    allowed_tools: list[str] | None = None
    has_scripts: bool = False
    executable_approved: bool = False
    executable_approved_at: datetime | None = None
    content_hash: str = ""
    id: UUID | None = None
    created_at: datetime | None = None
    approved_at: datetime | None = None
    last_checked_at: datetime | None = None
    last_check_error: str | None = None
    reference_files: list[ReferenceFile] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.slug:
            self.slug = slugify(self.name)
        if not self.content_hash:
            self.content_hash = compute_content_hash(
                self.name, self.description, self.instructions, self.allowed_tools
            )


@dataclass
class SkillScript:
    filename: str
    content: bytes
    skill_id: UUID | None = None
    id: UUID | None = None


@dataclass
class SkillReview:
    skill_id: UUID
    content_snapshot: dict
    decision: str  # "approved" | "rejected"
    id: UUID | None = None
    decided_at: datetime | None = None


@dataclass
class SkillMatch:
    """Intermediate result of `SkillMatcher.match()` — not persisted. Feeds
    `AgentContext.active_skills`/`skill_tool_names` and `SkillUsageTrace` construction
    (one `SkillMatch` -> one `SkillUsageTrace`)."""

    skill: Skill
    trigger: SkillTrigger
    similarity: float | None = None
