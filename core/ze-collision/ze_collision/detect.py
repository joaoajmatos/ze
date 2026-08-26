"""Cross-function contribution collision detection (Phase 126).

`submit_and_detect_collisions()` wraps `ze_plugin.contribution.validate_and_submit()`
without altering it (FR-001): it delegates for validation/persistence, then — only
after a successful write, fully fail-open — checks whether the new contribution
genuinely conflicts (NLI-flagged, not mere co-occurrence) with a recently-submitted
contribution from a *different* `source_function` on the same world-state face
(FR-002/FR-007), logging a `CollisionLogEntry` when it does. Never blocks, delays,
or resolves either write.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TypeVar
from uuid import UUID

from ze_agents.nli import NLIClient
from ze_agents.tasks import fire_and_forget
from ze_logging import get_logger
from ze_plugin.contribution import Contribution, validate_and_submit

from ze_collision.store import CollisionLogStore
from ze_collision.types import CollisionCandidate, CollisionLogEntry

log = get_logger(__name__)

T = TypeVar("T")

_COLLISION_WINDOW_HOURS = 24.0
_CONTRADICTION_THRESHOLD = 0.60
_NLI_TIMEOUT_SECONDS = 3.0
_MAX_SUMMARY_LEN = 500

# Single-process, in-memory recency window — data/cache state for the candidate
# scan, not a DI service singleton (data-model.md: "Held in a small in-process
# bounded structure... single-process, no cross-process coordination needed").
# Each entry is (monotonic insertion time, candidate) — the timestamp is pruning
# bookkeeping, kept out of the `CollisionCandidate` dataclass itself.
_window: list[tuple[float, CollisionCandidate]] = []


@dataclass
class _CandidateMatch:
    candidate: CollisionCandidate
    matched_entity_id: UUID | None


def _prune_window() -> None:
    cutoff = time.monotonic() - _COLLISION_WINDOW_HOURS * 3600
    while _window and _window[0][0] < cutoff:
        _window.pop(0)


def _find_candidates(new: CollisionCandidate) -> list[_CandidateMatch]:
    _prune_window()
    matches: list[_CandidateMatch] = []
    for _inserted_at, existing in _window:
        if existing.source_function == new.source_function:
            continue  # FR-002/FR-007 — same source_function never a candidate pair
        if existing.target_face != new.target_face:
            continue

        shared_entity: UUID | None = None
        if new.entity_ids and existing.entity_ids:
            shared = set(new.entity_ids) & set(existing.entity_ids)
            if shared:
                shared_entity = next(iter(shared))
            else:
                continue  # both sides have entity links but they don't overlap
        elif new.entity_ids or existing.entity_ids:
            continue  # one side is entity-linked, the other isn't — no match
        # else: neither side has entity_ids — fall back to target_face match only

        matches.append(
            _CandidateMatch(candidate=existing, matched_entity_id=shared_entity)
        )
    return matches


def _conflict_summary(a: CollisionCandidate, b: CollisionCandidate) -> str:
    summary = (
        f"{a.source_function}/{a.claim_kind} vs {b.source_function}/{b.claim_kind}: "
        f"{a.content!r} vs {b.content!r}"
    )
    return summary[:_MAX_SUMMARY_LEN]


async def _check_for_collisions(
    new: CollisionCandidate,
    collision_store: CollisionLogStore,
    nli_client: NLIClient,
) -> None:
    try:
        candidate_matches = _find_candidates(new)
        if new.content is not None:
            for match in candidate_matches:
                other = match.candidate
                if other.content is None:
                    continue
                try:
                    scores = await asyncio.wait_for(
                        nli_client.scores([(other.content, new.content)]),
                        timeout=_NLI_TIMEOUT_SECONDS,
                    )
                except Exception as exc:
                    log.warning("collision_nli_check_failed", error=str(exc))
                    continue

                if not scores or scores[0] is None:
                    continue
                if scores[0].get("contradiction", 0.0) < _CONTRADICTION_THRESHOLD:
                    continue

                entry = CollisionLogEntry(
                    id=None,
                    contribution_a_domain_id=other.domain_id,
                    contribution_a_producer_kind=other.producer_kind,
                    contribution_a_source_function=other.source_function,
                    contribution_a_claim_kind=other.claim_kind,
                    contribution_b_domain_id=new.domain_id,
                    contribution_b_producer_kind=new.producer_kind,
                    contribution_b_source_function=new.source_function,
                    contribution_b_claim_kind=new.claim_kind,
                    matched_entity_id=match.matched_entity_id,
                    matched_target_face=new.target_face,
                    conflict_summary=_conflict_summary(other, new),
                    created_at=None,
                )
                try:
                    await collision_store.log(entry)
                except Exception as exc:
                    log.warning("collision_log_write_failed", error=str(exc))
    except Exception as exc:
        log.warning("collision_check_failed", error=str(exc))
    finally:
        _window.append((time.monotonic(), new))


async def submit_and_detect_collisions(
    contribution: Contribution,
    write: Callable[[], Awaitable[T]],
    *,
    result_id: Callable[[T], UUID],
    producer_kind: str,
    check_fact_exists: Callable[[UUID], Awaitable[bool]] | None = None,
    check_episode_exists: Callable[[UUID], Awaitable[bool]] | None = None,
    check_signal_exists: Callable[[UUID], Awaitable[bool]] | None = None,
    collision_store: CollisionLogStore | None = None,
    nli_client: NLIClient | None = None,
) -> T:
    """Delegate to `validate_and_submit`, then fire-and-forget a collision check.

    `collision_store`/`nli_client` are optional — omitting either makes this
    function behave identically to plain `validate_and_submit` (fail-open,
    opt-in; not every call site is wired to a live store/NLI client yet).
    """
    result = await validate_and_submit(
        contribution,
        write,
        check_fact_exists=check_fact_exists,
        check_episode_exists=check_episode_exists,
        check_signal_exists=check_signal_exists,
    )

    if collision_store is not None and nli_client is not None:
        candidate = CollisionCandidate(
            domain_id=result_id(result),
            producer_kind=producer_kind,
            source_function=contribution.source_function,
            claim_kind=contribution.claim_kind,
            target_face=contribution.target_face,
            content=contribution.content,
            entity_ids=list(contribution.entity_ids),
            submitted_at=datetime.now(timezone.utc),
        )
        fire_and_forget(
            _check_for_collisions(candidate, collision_store, nli_client),
            label="collision_check",
        )

    return result
