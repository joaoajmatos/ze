from __future__ import annotations

from typing import Protocol
from uuid import UUID

from ze_correlation.store import HypothesisNotFoundError, PostgresHypothesisStore
from ze_correlation.types import EvidenceRef, Hypothesis


class HypothesisStore(Protocol):
    """Contract a plugin depends on to read/write `Hypothesis` rows.

    Satisfied by `ze_correlation.store.PostgresHypothesisStore`, wired at
    `apps/ze-api/ze_api/container.py` — the same DI shape as every other
    store Protocol in this codebase.
    """

    async def save(self, hypothesis: Hypothesis) -> None: ...

    async def get(self, hypothesis_id: UUID) -> Hypothesis | None: ...

    async def list_by_entities(self, entity_ids: list[UUID]) -> list[Hypothesis]: ...

    async def update_evidence(
        self, hypothesis_id: UUID, evidence: list[EvidenceRef], confidence: float
    ) -> None: ...

    async def confirm(self, hypothesis_id: UUID) -> Hypothesis: ...

    async def mark_promoted(self, hypothesis_id: UUID) -> Hypothesis: ...


__all__ = [
    "Hypothesis",
    "EvidenceRef",
    "HypothesisStore",
    "PostgresHypothesisStore",
    "HypothesisNotFoundError",
]
