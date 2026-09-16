"""Conversion from ze-memory domain types into the shared `Contribution` seam type."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from ze_agents.claims import ClaimKind, Confidence, DecayProfile, Provenance
from ze_agents.errors import ContributionError
from ze_collision.detect import submit_and_detect_collisions
from ze_logging import get_logger
from ze_plugin.contribution import (
    Contribution,
    EvidenceRef,
    SourceFunction,
    TargetFace,
)

from ze_memory.errors import StoreError
from ze_memory.types import Fact, Signal

log = get_logger(__name__)


@dataclass
class PerceptionFactSubmit:
    fact: Fact
    provenance: Provenance
    target_face: TargetFace
    evidence: list[EvidenceRef]


def signal_to_contribution(signal: Signal) -> Contribution:
    return Contribution(
        claim_kind=ClaimKind.FACT,
        provenance=signal.provenance,
        confidence=Confidence(
            value=signal.confidence,
            decay_profile=DecayProfile.TIME_LINEAR,
        ),
        target_face=TargetFace.WORLD,
        source_function=SourceFunction.PERCEPTION,
        evidence=[],
        content=f"{signal.title} {signal.summary}",
        # Entity resolution for signals happens *after* this write, inside
        # retriever.py's `ingest_signal` — so matching falls back to
        # `target_face` here per FR-002. Intentional, not a gap.
        entity_ids=[],
    )


def fact_to_contribution(
    fact: Fact,
    *,
    provenance: Provenance,
    target_face: TargetFace,
    evidence: list[EvidenceRef] | None = None,
) -> Contribution:
    content = f"{fact.predicate} {fact.value}".strip()
    entity_ids = [eid for eid in (fact.subject_id, fact.object_id) if eid is not None]
    return Contribution(
        claim_kind=ClaimKind.FACT,
        provenance=provenance,
        confidence=Confidence(
            value=fact.confidence,
            decay_profile=DecayProfile.TIME_LINEAR,
        ),
        target_face=target_face,
        source_function=SourceFunction.PERCEPTION,
        evidence=list(evidence or []),
        content=content,
        entity_ids=entity_ids,
    )


async def submit_perception_facts(
    store: Any,
    items: Sequence[PerceptionFactSubmit],
) -> None:
    """Validate each perception fact on the contribution seam, then persist.

    Copies envelope provenance onto `Fact.provenance` and stamps `claim_kind=FACT`.
    """
    for item in items:
        fact = item.fact
        fact.provenance = item.provenance
        fact.claim_kind = ClaimKind.FACT
        contribution = fact_to_contribution(
            fact,
            provenance=item.provenance,
            target_face=item.target_face,
            evidence=item.evidence,
        )

        async def _write(fact: Fact = fact) -> UUID:
            fact_id = await store._write_fact_with_contradiction_check(fact)
            if fact_id is None:
                raise StoreError("perception fact insert returned no id")
            fact.id = fact_id
            return fact_id

        try:
            await submit_and_detect_collisions(
                contribution,
                _write,
                result_id=lambda fact_id: fact_id,
                producer_kind="fact",
                collision_store=getattr(store, "_collision_store", None),
                nli_client=getattr(store, "_nli", None),
            )
        except ContributionError:
            raise
        except Exception as exc:
            log.warning(
                "memory_propose_fact_failed",
                predicate=fact.predicate,
                error=str(exc),
            )
