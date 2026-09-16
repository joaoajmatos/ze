from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from ze_agents.claims import ClaimKind
from ze_automation.goals.store import GoalStore
from ze_automation.goals.types import EligibleLearning


@dataclass(frozen=True)
class LearningContextItem:
    id: UUID
    content: str
    claim_kind: ClaimKind
    relevance: float
    evidence_summary: str


class LearningContextAdapter:
    """Bounded read adapter for priority consumers.

    Returns labeled eligible learnings. Does not rank, notify, or write overrides.
    """

    def __init__(self, goal_store: GoalStore) -> None:
        self._goal_store = goal_store

    async def list_context(
        self, query: str = "", *, limit: int = 5
    ) -> list[LearningContextItem]:
        items: list[EligibleLearning] = await self._goal_store.list_eligible_learnings(
            query, limit=limit
        )
        return [
            LearningContextItem(
                id=item.id,
                content=item.content,
                claim_kind=item.claim_kind,
                relevance=item.relevance,
                evidence_summary=item.evidence_summary,
            )
            for item in items
        ]
