from __future__ import annotations

from typing import Any
from uuid import UUID as UUIDType

from pydantic import BaseModel


class ContributionRefSchema(BaseModel):
    domain_id: UUIDType
    producer_kind: str
    source_function: str
    claim_kind: str


class CollisionLogEntrySchema(BaseModel):
    id: UUIDType
    contribution_a: ContributionRefSchema
    contribution_b: ContributionRefSchema
    matched_entity_id: UUIDType | None
    matched_target_face: str
    conflict_summary: str
    created_at: str

    @classmethod
    def from_entry(cls, entry: Any) -> CollisionLogEntrySchema:
        return cls(
            id=entry.id,
            contribution_a=ContributionRefSchema(
                domain_id=entry.contribution_a_domain_id,
                producer_kind=entry.contribution_a_producer_kind,
                source_function=entry.contribution_a_source_function.value,
                claim_kind=entry.contribution_a_claim_kind.value,
            ),
            contribution_b=ContributionRefSchema(
                domain_id=entry.contribution_b_domain_id,
                producer_kind=entry.contribution_b_producer_kind,
                source_function=entry.contribution_b_source_function.value,
                claim_kind=entry.contribution_b_claim_kind.value,
            ),
            matched_entity_id=entry.matched_entity_id,
            matched_target_face=entry.matched_target_face.value,
            conflict_summary=entry.conflict_summary,
            created_at=entry.created_at.isoformat() if entry.created_at else "",
        )
