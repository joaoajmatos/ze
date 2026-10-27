"""The one write surface for open loops: every domain event is one transaction.

Rules per event: `rules.EVENT_RULES`. A refused move raises
`InvalidLoopTransitionError`, a missing loop `LoopNotFoundError`; a race that left
nothing to do returns `None` or `False`. Each method returns the loop as stored.

Entity resolution, matching, embeddings, judgments and title writing all run before
an event is called: a transaction holds only SQL.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from ze_agents.db import DBPool
from ze_logging import get_logger
from ze_plugin.contribution import EvidenceRef

from ze_worldstate.types import OpenLoop, SourceKey

log = get_logger(__name__)


@dataclass(frozen=True)
class LoopDraft:
    title: str
    provenance: str
    evidence: tuple[EvidenceRef, ...] = ()
    entity_ids: tuple[UUID, ...] = ()
    source: SourceKey | None = None


@dataclass(frozen=True)
class Corroboration:
    evidence: tuple[EvidenceRef, ...]
    entity_ids: tuple[UUID, ...]
    key: SourceKey
    same_concern: float
    confidence: float | None = None  # CORROBORATE: the raised value; PROMOTE: ignored
    model: str | None = None
    latency_ms: int | None = None


@dataclass(frozen=True)
class SourceWrite:
    outcome: Literal["corroborate", "promote", "duplicate_source", "lost_race"]
    loop: OpenLoop


@dataclass(frozen=True)
class Tracked:
    outcome: str  # TrackOutcome.CONFIRMED | REINFORCED | REVIVED
    loop: OpenLoop


class LoopLifecycle:
    def __init__(
        self,
        pool: DBPool,
        *,
        memory_store: Any = None,  # existence checkers for the contribution seam
        collision_store: Any = None,  # set late by wire_collision_detection
        nli_client: Any = None,
    ) -> None:
        self._pool = pool
        self._memory_store = memory_store
        self.collision_store = collision_store
        self._nli_client = nli_client

    async def create_suspected(self, draft: LoopDraft) -> OpenLoop:
        """Insert a suspected loop at 0.3 through the contribution seam.

        One transaction: the row, evidence links, entity links, and the origin
        source when `draft.source` has a ref. The contribution carries the draft's
        evidence, and the seam checks that it exists.
        """
        raise NotImplementedError

    async def create_declared(
        self, draft: LoopDraft, *, window_days: int | None = None
    ) -> OpenLoop:
        """Insert an active loop with the declared stamp through the contribution seam.

        Same transaction and same checks as `create_suspected`. The window is
        `window_days` or 7. An inflow passes the draft's provenance as stored
        (`user_declared` for the conversation inflow).
        """
        raise NotImplementedError

    async def confirm(self, loop_id: UUID) -> OpenLoop:
        """Suspected -> active with the declared stamp (window 7). One guarded UPDATE.

        Refused from every other state.
        """
        raise NotImplementedError

    async def track(
        self, loop_id: UUID, *, window_days: int, entity_ids: Sequence[UUID] = ()
    ) -> Tracked:
        """The user asked Ze to keep a loop in mind.

        Suspected: `confirmed`; drifting: `revived`; both take the declared stamp with
        `window_days`. Active: `reinforced`, confidence `max(c, 0.9)`, deadline untouched.
        Entity links in the same transaction. Refused from closed and dropped.
        """
        raise NotImplementedError

    async def close(self, loop_id: UUID) -> OpenLoop:
        """The user closes an active or drifting loop: state and `closed_at`."""
        raise NotImplementedError

    async def drop(self, loop_id: UUID) -> OpenLoop:
        """Suspected, active or drifting -> dropped.

        Under the row lock: reads the loop's evidence and writes state, `closed_at`
        and the evidence fingerprint in one statement. An empty set writes the
        fingerprint of nothing, as today.
        """
        raise NotImplementedError

    async def link(
        self,
        loop_id: UUID,
        *,
        reminder_id: UUID | None = None,
        goal_id: UUID | None = None,
    ) -> bool:
        """Set the reminder or goal pointer once on a live loop; never overwrite.

        Returns whether anything changed; closed and dropped loops return False.
        """
        raise NotImplementedError

    async def note_evidence(
        self,
        loop_id: UUID,
        *,
        evidence: Sequence[EvidenceRef],
        entity_ids: Sequence[UUID],
    ) -> OpenLoop:
        """Link evidence and entities to a live loop.

        An active loop with evidence also moves its drift deadline to
        `GREATEST(COALESCE(deadline, now()), now() + 7d)` (phase 170). One transaction.
        """
        raise NotImplementedError

    async def corroborate(
        self, loop_id: UUID, corroboration: Corroboration
    ) -> SourceWrite:
        """An independent source matched a suspected loop (phase 172).

        One transaction: evidence and entity links, the corroboration source row, and
        `corroboration.confidence`. A source key the loop already has writes no
        confidence and reports `duplicate_source`.
        """
        raise NotImplementedError

    async def promote(self, loop_id: UUID, corroboration: Corroboration) -> SourceWrite:
        """Suspected -> active at `GREATEST(confidence, 0.7)`, window 7 (phase 172).

        One transaction: links, the source row (`promoted = true` only on a win), and the
        guarded stamp. If another inflow promoted first, the source row keeps
        `promoted = false`, no confidence or state is written, and the outcome is `lost_race`.
        """
        raise NotImplementedError

    async def resolve(
        self, loop_id: UUID, *, evidence: Sequence[EvidenceRef]
    ) -> OpenLoop | None:
        """Suspected, active or drifting -> closed on resolving evidence (phase 199).

        State, `closed_at` and the evidence links in one transaction. Never a
        fingerprint: the loop was done, not wrong. Closed and dropped return `None`.
        """
        raise NotImplementedError

    async def decay_from_evidence(
        self, evidence_type: str, evidence_id: UUID
    ) -> list[OpenLoop]:
        """Lower the confidence of every loop that cites contradicted evidence.

        Per loop, under the row lock: read confidence and evidence count, write the new
        confidence, and for an active loop the move to drifting with the contradiction
        rationale, in one statement. Other states take the confidence alone.
        """
        raise NotImplementedError

    async def drift(self, loop_id: UUID) -> OpenLoop | None:
        """Active -> drifting with the absence rationale when `drift_deadline <= now()`.

        A loop confirmed again after the sweep read it returns `None`.
        """
        raise NotImplementedError

    async def expire(self, loop_id: UUID) -> OpenLoop | None:
        """A stale suspected loop -> dropped, with the evidence fingerprint.

        An expiry with no evidence writes a `NULL` fingerprint, so it blocks nothing.
        Any other state returns `None`.
        """
        raise NotImplementedError
