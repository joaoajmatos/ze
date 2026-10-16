from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID as UUIDType

from pydantic import (
    BaseModel,
)

SourceKindLiteral = Literal["loop", "goal", "hypothesis", "relationship"]


class PriorityOverrideSchema(BaseModel):
    id: UUIDType
    pinned: bool
    anchor_source_kind: SourceKindLiteral
    anchor_source_id: UUIDType
    relation: Literal["above", "below"]
    submitted_at: datetime


class PrioritySnapshotItem(BaseModel):
    source_kind: SourceKindLiteral
    source_id: UUIDType
    title: str
    displayed_rank: int
    computed_rank: int
    overridden_from_computed: bool
    override: PriorityOverrideSchema | None

    @classmethod
    def from_merged_item(cls, item: Any) -> "PrioritySnapshotItem":
        return cls(
            source_kind=item.source_kind,
            source_id=item.source_id,
            title=item.title,
            displayed_rank=item.displayed_rank,
            computed_rank=item.computed_rank,
            overridden_from_computed=item.overridden_from_computed,
            override=PriorityOverrideSchema(
                id=item.override.id,
                pinned=item.override.pinned,
                anchor_source_kind=item.override.anchor_source_kind,
                anchor_source_id=item.override.anchor_source_id,
                relation=item.override.relation,
                submitted_at=item.override.submitted_at,
            )
            if item.override is not None
            else None,
        )


class PrioritySnapshotResponse(BaseModel):
    items: list[PrioritySnapshotItem]
    sources_failed: list[SourceKindLiteral]


class PriorityOverrideRequestSchema(BaseModel):
    source_kind: SourceKindLiteral
    source_id: UUIDType
    anchor_source_kind: SourceKindLiteral
    anchor_source_id: UUIDType
    relation: Literal["above", "below"]
    pinned: bool = False
