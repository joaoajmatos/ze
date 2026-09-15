"""Shared promotion path — used by both `SocialCooccurrenceJob` (on
corroboration) and `confirm_project_membership` (on explicit user confirm),
per research.md Decision 5 / tasks.md T024's "one code path" requirement."""

from __future__ import annotations

from typing import Any

from ze_logging import get_logger
from ze_memory.graph.predicates import COLLABORATES_WITH, WORKS_ON
from ze_plugin.contribution import EvidenceRef as ContributionEvidenceRef

from ze_correlation.types import Hypothesis
from ze_personal.graph.memory_hooks import write_relationship_edge_via_seam

log = get_logger(__name__)


async def promote_hypothesis(
    hypothesis: Hypothesis,
    *,
    hypothesis_store: Any,
    memory_store: Any,
    collision_store: Any = None,
    nli_client: Any = None,
) -> None:
    """Write the `WORKS_ON`/`COLLABORATES_WITH` identity edge for `hypothesis`
    and mark it `promoted_at`. No-op if already promoted (idempotency guard,
    data-model.md)."""
    if hypothesis.promoted_at is not None:
        return
    if len(hypothesis.entities) != 2:
        log.warning(
            "hypothesis_promotion_skipped_bad_entity_count",
            hypothesis_id=str(hypothesis.id),
            entity_count=len(hypothesis.entities),
        )
        return

    source_id, target_id = hypothesis.entities
    target_entity = await memory_store.get_entity(target_id)
    is_project = target_entity is not None and target_entity.entity_type == "project"
    predicate = WORKS_ON if is_project else COLLABORATES_WITH
    target_type = "project" if is_project else "person"

    evidence = [
        ContributionEvidenceRef(kind=e.kind, id=e.id) for e in hypothesis.evidence
    ]

    await write_relationship_edge_via_seam(
        memory_store,
        source_id=source_id,
        target_id=target_id,
        target_type=target_type,
        predicate=predicate,
        confidence=hypothesis.confidence,
        evidence=evidence,
        collision_store=collision_store,
        nli_client=nli_client,
    )
    await hypothesis_store.mark_promoted(hypothesis.id)
    log.info("hypothesis_promoted", hypothesis_id=str(hypothesis.id), predicate=predicate)
