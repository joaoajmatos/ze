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

from ze_agents.claims import DecayProfile, decay
from ze_agents.db import DBPool
from ze_collision.detect import submit_and_detect_collisions
from ze_logging import get_logger
from ze_plugin.contribution import EvidenceRef

from ze_worldstate import drift as drift_rationale
from ze_worldstate.contribution import loop_to_contribution
from ze_worldstate.errors import InvalidLoopTransitionError, LoopNotFoundError
from ze_worldstate.fingerprint import compute_evidence_fingerprint
from ze_worldstate.lifecycle.rules import (
    CONFIDENCE_STAMP,
    PROMOTED_CONFIDENCE,
    SUSPECTED_CONFIDENCE,
    DeclaredStamp,
    LoopEvent,
    Verdict,
    allowed_from,
    verdict,
)
from ze_worldstate.store import loop_from_row
from ze_worldstate.types import (
    LoopSourceRole,
    LoopState,
    OpenLoop,
    SourceKey,
    TrackOutcome,
)

log = get_logger(__name__)

_DERIVED_FROM_SQL = """
    INSERT INTO memory_relationships
      (source_id, source_type, predicate, target_id, target_type,
       confidence, creation_method)
    VALUES ($1, 'open_loop', 'derived_from', $2, $3, 1.0, 'extracted')
    ON CONFLICT (source_id, predicate, target_id) WHERE target_id IS NOT NULL
    DO NOTHING
"""
_HAS_OPEN_LOOP_SQL = """
    INSERT INTO memory_relationships
      (source_id, source_type, predicate, target_id, target_type,
       confidence, creation_method)
    VALUES ($1, 'entity', 'has_open_loop', $2, 'open_loop', 1.0, 'extracted')
    ON CONFLICT (source_id, predicate, target_id) WHERE target_id IS NOT NULL
    DO NOTHING
"""
_SOURCE_SQL = """
    INSERT INTO open_loop_sources
      (loop_id, role, inflow, source_ref, evidence_kind, evidence_id,
       same_concern, promoted, model, latency_ms)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
    ON CONFLICT (loop_id, inflow, source_ref) DO NOTHING
    RETURNING id
"""


def _existence_checkers(memory_store: Any):
    async def _check_fact_exists(fact_id: UUID) -> bool:
        if memory_store is None:
            return False
        return len(await memory_store.get_facts_by_ids([fact_id])) > 0

    async def _check_episode_exists(episode_id: UUID) -> bool:
        if memory_store is None:
            return False
        return len(await memory_store.get_episodes_by_ids([episode_id])) > 0

    return _check_fact_exists, _check_episode_exists


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

    @staticmethod
    async def _lock(conn: Any, loop_id: UUID) -> Any:
        row = await conn.fetchrow(
            "SELECT * FROM open_loops WHERE id = $1 FOR UPDATE", loop_id
        )
        if row is None:
            raise LoopNotFoundError(f"Loop {loop_id} not found")
        return row

    @staticmethod
    def _verdict(event: LoopEvent, row: Any) -> Verdict:
        """The rule for this event from the locked row's state; a refusal raises."""
        state = LoopState(row["state"])
        result = verdict(event, state)
        if result is Verdict.REFUSED:
            raise InvalidLoopTransitionError(
                f"Cannot {event.value} loop {row['id']} from {state.value}"
            )
        return result

    @staticmethod
    def _stored(event: LoopEvent, before: Any, after: Any) -> OpenLoop:
        """Log the write once and return the row as stored."""
        loop = loop_from_row(after)
        if before["state"] != after["state"]:
            log.info(
                "open_loop_transitioned",
                loop_id=str(loop.id),
                from_state=before["state"],
                to_state=after["state"],
                via=event.value,
            )
        else:
            log.info("open_loop_updated", loop_id=str(loop.id), via=event.value)
        return loop

    @staticmethod
    def _allowed(event: LoopEvent) -> list[str]:
        return [state.value for state in allowed_from(event)]

    @staticmethod
    async def _evidence(conn: Any, loop_id: UUID) -> list[EvidenceRef]:
        rows = await conn.fetch(
            "SELECT target_type, target_id FROM memory_relationships"
            " WHERE source_id = $1 AND source_type = 'open_loop'"
            " AND predicate = 'derived_from'",
            loop_id,
        )
        return [EvidenceRef(kind=r["target_type"], id=r["target_id"]) for r in rows]

    @staticmethod
    async def _link(
        conn: Any,
        loop_id: UUID,
        evidence: Sequence[EvidenceRef],
        entity_ids: Sequence[UUID],
    ) -> None:
        for ref in evidence:
            await conn.execute(_DERIVED_FROM_SQL, loop_id, ref.id, ref.kind)
        for entity_id in entity_ids:
            await conn.execute(_HAS_OPEN_LOOP_SQL, entity_id, loop_id)

    @staticmethod
    async def _add_source(
        conn: Any,
        loop_id: UUID,
        role: LoopSourceRole,
        key: SourceKey,
        evidence: EvidenceRef | None,
        *,
        same_concern: float | None = None,
        promoted: bool = False,
        model: str | None = None,
        latency_ms: int | None = None,
    ) -> bool:
        """Insert a source row; False when this loop already counted the key."""
        row = await conn.fetchrow(
            _SOURCE_SQL,
            loop_id,
            role.value,
            key.inflow,
            key.ref,
            evidence.kind if evidence else None,
            evidence.id if evidence else None,
            same_concern,
            promoted,
            model,
            latency_ms,
        )
        return row is not None

    async def _create(
        self, draft: LoopDraft, *, declared: bool, window_days: int | None
    ) -> OpenLoop:
        event = LoopEvent.CREATE_DECLARED if declared else LoopEvent.CREATE_SUSPECTED
        state = LoopState.ACTIVE if declared else LoopState.SUSPECTED
        confidence = DeclaredStamp.CONFIDENCE if declared else SUSPECTED_CONFIDENCE
        window = window_days or DeclaredStamp.DEFAULT_WINDOW_DAYS
        contribution = loop_to_contribution(
            OpenLoop(
                title=draft.title,
                provenance=draft.provenance,
                confidence=confidence,
                state=state,
            ),
            evidence=list(draft.evidence),
            entity_ids=list(draft.entity_ids),
        )

        async def write() -> OpenLoop:
            async with self._pool.acquire() as conn, conn.transaction():
                if declared:
                    row = await conn.fetchrow(
                        "INSERT INTO open_loops"
                        " (title, state, provenance, confidence, confirmed_at, drift_deadline)"
                        " VALUES ($1, 'active', $2, $3, now(),"
                        " now() + make_interval(days => $4)) RETURNING *",
                        draft.title,
                        draft.provenance,
                        confidence,
                        window,
                    )
                else:
                    row = await conn.fetchrow(
                        "INSERT INTO open_loops (title, state, provenance, confidence)"
                        " VALUES ($1, 'suspected', $2, $3) RETURNING *",
                        draft.title,
                        draft.provenance,
                        confidence,
                    )
                await self._link(conn, row["id"], draft.evidence, draft.entity_ids)
                if draft.source is not None and draft.source.ref:
                    await self._add_source(
                        conn,
                        row["id"],
                        LoopSourceRole.ORIGIN,
                        draft.source,
                        draft.evidence[0] if draft.evidence else None,
                    )
            created = loop_from_row(row)
            log.info(
                "open_loop_created",
                loop_id=str(created.id),
                state=created.state.value,
                provenance=created.provenance,
                via=event.value,
            )
            return created

        check_fact_exists, check_episode_exists = _existence_checkers(self._memory_store)
        return await submit_and_detect_collisions(
            contribution,
            write,
            result_id=lambda loop: loop.id,
            producer_kind="open_loop",
            check_fact_exists=check_fact_exists,
            check_episode_exists=check_episode_exists,
            collision_store=self.collision_store,
            nli_client=self._nli_client,
        )

    async def _write(
        self, conn: Any, event: LoopEvent, before: Any, set_sql: str, *params: Any
    ) -> OpenLoop:
        """One guarded UPDATE on the locked row; `$1` is the id, `$2` the allowed states."""
        sets = ", ".join(filter(None, (set_sql, "updated_at = now()")))
        after = await conn.fetchrow(
            f"UPDATE open_loops SET {sets}"
            " WHERE id = $1 AND state = ANY($2::text[]) RETURNING *",
            before["id"],
            self._allowed(event),
            *params,
        )
        if after is None:
            raise InvalidLoopTransitionError(
                f"Loop {before['id']} changed state before it could {event.value}"
            )
        return self._stored(event, before, after)

    async def create_suspected(self, draft: LoopDraft) -> OpenLoop:
        """Insert a suspected loop at 0.3 through the contribution seam.

        One transaction: the row, evidence links, entity links, and the origin
        source when `draft.source` has a ref. The contribution carries the draft's
        evidence, and the seam checks that it exists.
        """
        return await self._create(draft, declared=False, window_days=None)

    async def create_declared(
        self, draft: LoopDraft, *, window_days: int | None = None
    ) -> OpenLoop:
        """Insert an active loop with the declared stamp through the contribution seam.

        Same transaction and same checks as `create_suspected`. The window is
        `window_days` or 7. An inflow passes the draft's provenance as stored
        (`user_declared` for the conversation inflow).
        """
        return await self._create(draft, declared=True, window_days=window_days)

    async def confirm(self, loop_id: UUID) -> OpenLoop:
        """Suspected -> active with the declared stamp (window 7). One guarded UPDATE.

        Refused from every other state.
        """
        async with self._pool.acquire() as conn, conn.transaction():
            row = await self._lock(conn, loop_id)
            self._verdict(LoopEvent.CONFIRM, row)
            return await self._write(
                conn,
                LoopEvent.CONFIRM,
                row,
                "state = 'active', "
                + DeclaredStamp.sql("$3", "$4"),
                DeclaredStamp.CONFIDENCE,
                DeclaredStamp.DEFAULT_WINDOW_DAYS,
            )

    async def track(
        self, loop_id: UUID, *, window_days: int, entity_ids: Sequence[UUID] = ()
    ) -> Tracked:
        """The user asked Ze to keep a loop in mind.

        Suspected: `confirmed`; drifting: `revived`; both take the declared stamp with
        `window_days`. Active: `reinforced`, confidence raised to the declared level, deadline untouched.
        Entity links in the same transaction. Refused from closed and dropped.
        """
        async with self._pool.acquire() as conn, conn.transaction():
            row = await self._lock(conn, loop_id)
            if self._verdict(LoopEvent.TRACK, row) is Verdict.MOVE:
                outcome = (
                    TrackOutcome.REVIVED
                    if row["state"] == LoopState.DRIFTING.value
                    else TrackOutcome.CONFIRMED
                )
                loop = await self._write(
                    conn,
                    LoopEvent.TRACK,
                    row,
                    "state = 'active', " + DeclaredStamp.sql("$3", "$4"),
                    DeclaredStamp.CONFIDENCE,
                    window_days,
                )
            else:
                outcome = TrackOutcome.REINFORCED
                loop = await self._write(
                    conn,
                    LoopEvent.TRACK,
                    row,
                    CONFIDENCE_STAMP.format(new="GREATEST(confidence, $3)"),
                    DeclaredStamp.CONFIDENCE,
                )
            await self._link(conn, loop_id, (), entity_ids)
        return Tracked(outcome, loop)

    async def close(self, loop_id: UUID) -> OpenLoop:
        """The user closes an active or drifting loop: state and `closed_at`."""
        async with self._pool.acquire() as conn, conn.transaction():
            row = await self._lock(conn, loop_id)
            self._verdict(LoopEvent.CLOSE, row)
            return await self._write(
                conn, LoopEvent.CLOSE, row, "state = 'closed', closed_at = now()"
            )

    async def drop(self, loop_id: UUID) -> OpenLoop:
        """Suspected, active or drifting -> dropped.

        Under the row lock: reads the loop's evidence and writes state, `closed_at`
        and the evidence fingerprint in one statement. An empty set writes the
        fingerprint of nothing, as today.
        """
        async with self._pool.acquire() as conn, conn.transaction():
            row = await self._lock(conn, loop_id)
            self._verdict(LoopEvent.DROP, row)
            fingerprint = compute_evidence_fingerprint(
                await self._evidence(conn, loop_id)
            )
            return await self._write(
                conn,
                LoopEvent.DROP,
                row,
                "state = 'dropped', closed_at = now(),"
                " dismissed_evidence_fingerprint = $3",
                fingerprint,
            )

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
        if reminder_id is None and goal_id is None:
            return False
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "UPDATE open_loops SET reminder_id = COALESCE(reminder_id, $3),"
                " goal_id = COALESCE(goal_id, $4), updated_at = now()"
                " WHERE id = $1 AND state = ANY($2::text[])"
                " AND (reminder_id IS DISTINCT FROM COALESCE(reminder_id, $3)"
                " OR goal_id IS DISTINCT FROM COALESCE(goal_id, $4))"
                " RETURNING id",
                loop_id,
                self._allowed(LoopEvent.LINK),
                reminder_id,
                goal_id,
            )
        if row is not None:
            log.info("open_loop_updated", loop_id=str(loop_id), via=LoopEvent.LINK.value)
        return row is not None

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
        async with self._pool.acquire() as conn, conn.transaction():
            row = await self._lock(conn, loop_id)
            self._verdict(LoopEvent.NOTE_EVIDENCE, row)
            await self._link(conn, loop_id, evidence, entity_ids)
            moves_deadline = bool(evidence) and row["state"] == LoopState.ACTIVE.value
            return await self._write(
                conn,
                LoopEvent.NOTE_EVIDENCE,
                row,
                "drift_deadline = GREATEST(COALESCE(drift_deadline, now()),"
                " now() + make_interval(days => $3))"
                if moves_deadline
                else "",
                *([DeclaredStamp.DEFAULT_WINDOW_DAYS] if moves_deadline else []),
            )

    async def corroborate(
        self, loop_id: UUID, corroboration: Corroboration
    ) -> SourceWrite:
        """An independent source matched a suspected loop (phase 172).

        One transaction: evidence and entity links, the corroboration source row, and
        `corroboration.confidence`. A source key the loop already has writes no
        confidence and reports `duplicate_source`.
        """
        async with self._pool.acquire() as conn, conn.transaction():
            row = await self._lock(conn, loop_id)
            self._verdict(LoopEvent.CORROBORATE, row)
            await self._link(
                conn, loop_id, corroboration.evidence, corroboration.entity_ids
            )
            counted = await self._add_source(
                conn,
                loop_id,
                LoopSourceRole.CORROBORATION,
                corroboration.key,
                corroboration.evidence[0] if corroboration.evidence else None,
                same_concern=corroboration.same_concern,
                model=corroboration.model,
                latency_ms=corroboration.latency_ms,
            )
            if not counted or corroboration.confidence is None:
                after = await conn.fetchrow(
                    "UPDATE open_loops SET updated_at = now() WHERE id = $1 RETURNING *",
                    loop_id,
                )
                outcome = "duplicate_source" if not counted else "corroborate"
                return SourceWrite(outcome, self._stored(LoopEvent.CORROBORATE, row, after))
            loop = await self._write(
                conn,
                LoopEvent.CORROBORATE,
                row,
                CONFIDENCE_STAMP.format(new="$3"),
                corroboration.confidence,
            )
        return SourceWrite("corroborate", loop)

    async def promote(self, loop_id: UUID, corroboration: Corroboration) -> SourceWrite:
        """Suspected -> active at `GREATEST(confidence, 0.7)`, window 7 (phase 172).

        One transaction: links, the source row (`promoted = true` only on a win), and the
        guarded stamp. If another inflow promoted first, the source row keeps
        `promoted = false`, no confidence or state is written, and the outcome is `lost_race`.
        """
        async with self._pool.acquire() as conn, conn.transaction():
            row = await self._lock(conn, loop_id)
            won = self._verdict(LoopEvent.PROMOTE, row) is Verdict.MOVE
            await self._link(
                conn, loop_id, corroboration.evidence, corroboration.entity_ids
            )
            counted = await self._add_source(
                conn,
                loop_id,
                LoopSourceRole.CORROBORATION,
                corroboration.key,
                corroboration.evidence[0] if corroboration.evidence else None,
                same_concern=corroboration.same_concern,
                promoted=won,
                model=corroboration.model,
                latency_ms=corroboration.latency_ms,
            )
            if not counted or not won:
                after = await conn.fetchrow(
                    "UPDATE open_loops SET updated_at = now() WHERE id = $1 RETURNING *",
                    loop_id,
                )
                outcome = "duplicate_source" if not counted else "lost_race"
                return SourceWrite(outcome, self._stored(LoopEvent.PROMOTE, row, after))
            loop = await self._write(
                conn,
                LoopEvent.PROMOTE,
                row,
                "state = 'active', "
                + DeclaredStamp.sql("GREATEST(confidence, $3)", "$4"),
                PROMOTED_CONFIDENCE,
                DeclaredStamp.DEFAULT_WINDOW_DAYS,
            )
        return SourceWrite("promote", loop)

    async def resolve(
        self, loop_id: UUID, *, evidence: Sequence[EvidenceRef]
    ) -> OpenLoop | None:
        """Suspected, active or drifting -> closed on resolving evidence (phase 199).

        State, `closed_at` and the evidence links in one transaction. Never a
        fingerprint: the loop was done, not wrong. Closed and dropped return `None`.
        """
        async with self._pool.acquire() as conn, conn.transaction():
            row = await self._lock(conn, loop_id)
            if self._verdict(LoopEvent.RESOLVE, row) is Verdict.NO_CHANGE:
                return None
            loop = await self._write(
                conn,
                LoopEvent.RESOLVE,
                row,
                "state = 'closed', closed_at = now()",
            )
            await self._link(conn, loop_id, evidence, ())
        return loop

    async def decay_from_evidence(
        self, evidence_type: str, evidence_id: UUID
    ) -> list[OpenLoop]:
        """Lower the confidence of every loop that cites contradicted evidence.

        Per loop, under the row lock: read confidence and evidence count, write the new
        confidence, and for an active loop the move to drifting with the contradiction
        rationale, in one statement. Other states take the confidence alone.
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT ol.id FROM open_loops ol JOIN memory_relationships mr"
                " ON mr.source_id = ol.id WHERE mr.source_type = 'open_loop'"
                " AND mr.predicate = 'derived_from' AND mr.target_type = $1"
                " AND mr.target_id = $2",
                evidence_type,
                evidence_id,
            )
            updated: list[OpenLoop] = []
            for loop_id in {r["id"] for r in rows}:
                async with conn.transaction():
                    updated.append(
                        await self._decay_one(conn, loop_id, evidence_type, evidence_id)
                    )
            return updated

    async def _decay_one(
        self, conn: Any, loop_id: UUID, evidence_type: str, evidence_id: UUID
    ) -> OpenLoop:
        row = await self._lock(conn, loop_id)
        total = await conn.fetchval(
            "SELECT count(*) FROM memory_relationships WHERE source_id = $1"
            " AND source_type = 'open_loop' AND predicate = 'derived_from'",
            loop_id,
        )
        confidence = decay(
            row["confidence"],
            DecayProfile.EVIDENCE_WEIGHTED,
            remaining_evidence=total - 1,
            total_evidence=total,
        )
        stamp = CONFIDENCE_STAMP.format(new="$3")
        if verdict(LoopEvent.DECAY, LoopState(row["state"])) is Verdict.MOVE:
            loop = await self._write(
                conn,
                LoopEvent.DECAY,
                row,
                f"{stamp}, state = 'drifting', drift_rationale = $4",
                confidence,
                drift_rationale.compose_contradiction_rationale(
                    evidence_type, evidence_id
                ),
            )
        else:
            after = await conn.fetchrow(
                f"UPDATE open_loops SET {CONFIDENCE_STAMP.format(new='$2')}, updated_at = now()"
                " WHERE id = $1 RETURNING *",
                loop_id,
                confidence,
            )
            loop = self._stored(LoopEvent.DECAY, row, after)
        log.info(
            "open_loop_confidence_decayed",
            loop_id=str(loop_id),
            new_confidence=confidence,
            evidence_type=evidence_type,
            evidence_id=str(evidence_id),
        )
        return loop

    async def drift(self, loop_id: UUID) -> OpenLoop | None:
        """Active -> drifting with the absence rationale when `drift_deadline <= now()`.

        A loop confirmed again after the sweep read it returns `None`.
        """
        async with self._pool.acquire() as conn, conn.transaction():
            row = await self._lock(conn, loop_id)
            if self._verdict(LoopEvent.DRIFT, row) is Verdict.NO_CHANGE:
                return None
            absence = drift_rationale.compose_absence_rationale(loop_from_row(row))
            after = await conn.fetchrow(
                "UPDATE open_loops SET state = 'drifting', drift_rationale = $3,"
                " updated_at = now() WHERE id = $1 AND state = ANY($2::text[])"
                " AND drift_deadline <= now() RETURNING *",
                loop_id,
                self._allowed(LoopEvent.DRIFT),
                absence,
            )
            if after is None:
                return None
            return self._stored(LoopEvent.DRIFT, row, after)

    async def expire(self, loop_id: UUID) -> OpenLoop | None:
        """A stale suspected loop -> dropped, with the evidence fingerprint.

        An expiry with no evidence writes a `NULL` fingerprint, so it blocks nothing.
        Any other state returns `None`.
        """
        async with self._pool.acquire() as conn, conn.transaction():
            row = await self._lock(conn, loop_id)
            if self._verdict(LoopEvent.EXPIRE, row) is Verdict.NO_CHANGE:
                return None
            evidence = await self._evidence(conn, loop_id)
            fingerprint = compute_evidence_fingerprint(evidence) if evidence else None
            return await self._write(
                conn,
                LoopEvent.EXPIRE,
                row,
                "state = 'dropped', closed_at = now(),"
                " dismissed_evidence_fingerprint = $3",
                fingerprint,
            )
