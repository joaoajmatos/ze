from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class HypothesisEvidenceItem(BaseModel):
    kind: Literal["fact", "episode", "signal"]
    id: UUID
    label: str


class HypothesisEntityItem(BaseModel):
    id: UUID
    name: str | None


class HypothesisItem(BaseModel):
    id: UUID
    summary: str
    narrative: str
    relation: Literal["pattern", "causal_guess", "tension", "convergence"]
    confidence: float
    claim_kind: Literal["inference", "suspicion"]
    evidence: list[HypothesisEvidenceItem]
    entities: list[HypothesisEntityItem]
    surfaced: bool
    feedback: Literal["useful", "not_relevant", "muted"] | None
    confirmed: bool
    created_at: datetime


class HypothesisFeedbackRequest(BaseModel):
    feedback: Literal["useful", "not_relevant", "muted"] | None
