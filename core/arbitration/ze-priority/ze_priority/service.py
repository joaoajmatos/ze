"""`submit_reprioritization` — the one validated write path shared by the REST
route (US2) and the `reprioritize_item` conversational tool (US3), per FR-004."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from ze_agents.nli import NLIClient
from ze_collision.detect import submit_and_detect_collisions
from ze_collision.store import CollisionLogStore

from ze_priority.contribution import (
    override_to_contribution,
    synthesized_claim_contribution,
)
from ze_priority.errors import StaleReprioritizationTargetError
from ze_priority.store import PriorityOverrideStore
from ze_priority.types import PriorityOverride, PriorityOverrideRequest
from ze_priority.view import PriorityView

UTC = timezone.utc


async def submit_reprioritization(
    request: PriorityOverrideRequest,
    *,
    priority_view: PriorityView,
    override_store: PriorityOverrideStore,
    collision_store: CollisionLogStore | None = None,
    nli_client: NLIClient | None = None,
) -> PriorityOverride:
    ranking = await priority_view.rank()
    items_by_id = {item.source_id: item for item in ranking.items}

    item = items_by_id.get(request.source_id)
    anchor = items_by_id.get(request.anchor_source_id)
    if item is None or anchor is None:
        raise StaleReprioritizationTargetError(
            f"item {request.source_id} or anchor {request.anchor_source_id} is no "
            "longer present in any PriorityView source list"
        )

    override_id = uuid4()
    submitted_at = datetime.now(UTC)

    async def _write_override() -> PriorityOverride:
        return await override_store.create(
            PriorityOverride(
                id=override_id,
                source_kind=item.source_kind,
                source_id=item.source_id,
                anchor_source_kind=anchor.source_kind,
                anchor_source_id=anchor.source_id,
                relation=request.relation,
                pinned=request.pinned,
                submitted_at=submitted_at,
                superseded_at=None,
                contribution_domain_id=override_id,
            )
        )

    persisted = await submit_and_detect_collisions(
        override_to_contribution(item, anchor, request.relation, request.pinned),
        _write_override,
        result_id=lambda override: override.id,
        producer_kind="priority_override",
        collision_store=collision_store,
        nli_client=nli_client,
    )

    async def _write_synthesized_claim() -> object:
        return uuid4()

    await submit_and_detect_collisions(
        synthesized_claim_contribution(item),
        _write_synthesized_claim,
        result_id=lambda synthetic_id: synthetic_id,
        producer_kind="priority_view_computed",
        collision_store=collision_store,
        nli_client=nli_client,
    )

    return persisted
