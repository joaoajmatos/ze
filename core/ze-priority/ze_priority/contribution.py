"""Conversion of a reprioritization instruction into the shared `Contribution` seam
pair (data-model.md "Reprioritization Contribution pair"; research.md R1/R3/R4)."""

from __future__ import annotations

from ze_agents.claims import ClaimKind, Confidence, DecayProfile, Provenance
from ze_plugin.contribution import Contribution, SourceFunction, TargetFace

from ze_priority.types import PriorityItem


def override_to_contribution(
    item: PriorityItem,
    anchor: PriorityItem,
    relation: str,
    pinned: bool,
) -> Contribution:
    """The user-stated override contribution (`EXECUTIVE`/`PROMPT_SUPPLIED`)."""
    content = (
        f"{item.source_kind.capitalize()} {item.title!r} requested {relation} "
        f"{anchor.source_kind} {anchor.title!r}"
    )
    return Contribution(
        claim_kind=ClaimKind.PRIORITY,
        provenance=Provenance.PROMPT_SUPPLIED,
        confidence=Confidence(value=1.0, decay_profile=DecayProfile.TIME_LINEAR),
        target_face=TargetFace.ACTIVE_CONCERNS,
        source_function=SourceFunction.EXECUTIVE,
        content=content,
        entity_ids=[item.source_id],
    )


def synthesized_claim_contribution(item: PriorityItem) -> Contribution:
    """The companion contribution representing PriorityView's own current computed
    position for the same item (`EXECUTIVE`/`SYNTHESIZED`) — exists so Phase 126's
    collision detector can observe genuine user-vs-executive disagreement (R1)."""
    content = (
        f"Ze currently ranks {item.source_kind} {item.title!r} at position {item.rank}"
    )
    return Contribution(
        claim_kind=ClaimKind.PRIORITY,
        provenance=Provenance.SYNTHESIZED,
        confidence=item.priority,
        target_face=TargetFace.ACTIVE_CONCERNS,
        source_function=SourceFunction.EXECUTIVE,
        content=content,
        entity_ids=[item.source_id],
    )
