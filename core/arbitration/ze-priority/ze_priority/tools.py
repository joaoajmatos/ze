"""`reprioritize_item` — the conversational path's entry point (FR-003), per
contracts/tool-contract.md. Core tool (research.md R8), not a plugin tool."""

from __future__ import annotations

from typing import Any

import numpy as np

from ze_agents.nli import NLIClient
from ze_agents.tool import ToolAccess, tool
from ze_collision.store import CollisionLogStore
from ze_logging import get_logger

from ze_priority.errors import StaleReprioritizationTargetError
from ze_priority.store import PriorityOverrideStore
from ze_priority.types import PriorityItem, PriorityOverrideRequest
from ze_priority.service import submit_reprioritization
from ze_priority.view import PriorityView

log = get_logger(__name__)

_MATCH_FLOOR = 0.55
_MATCH_MARGIN = 0.05


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / denom) if denom else 0.0


def _disambiguate(
    item_description: str, items: list[PriorityItem], embedder: Any
) -> PriorityItem | None:
    if not items:
        return None
    query_vec = embedder.encode(item_description)
    scored = sorted(
        ((_cosine(query_vec, embedder.encode(item.title)), item) for item in items),
        key=lambda pair: pair[0],
        reverse=True,
    )
    top_score, top_item = scored[0]
    if top_score < _MATCH_FLOOR:
        return None
    if len(scored) > 1 and (top_score - scored[1][0]) < _MATCH_MARGIN:
        return None
    return top_item


def _resolve_anchor(
    target: PriorityItem, items: list[PriorityItem], requested_relation: str
) -> tuple[PriorityItem, str] | None:
    """Translate the coarse `requested_relation` into the anchor-relative
    representation the drag path produces (R3)."""
    ordered = sorted(items, key=lambda item: item.rank)
    index = next(
        i for i, item in enumerate(ordered) if item.source_id == target.source_id
    )

    if requested_relation == "more_urgent":
        if index == 0:
            return None  # already the top priority
        return ordered[index - 1], "above"
    if index == len(ordered) - 1:
        return None  # already the lowest priority
    return ordered[index + 1], "below"


@tool(
    access=ToolAccess.WRITE,
    description=(
        "Reprioritize an open loop, stuck goal, or hypothesis relative to Ze's "
        "current ranking — make it more urgent or less urgent. item_description "
        "is the user's own phrasing naming the target item; requested_relation is "
        "'more_urgent' or 'less_urgent'; pin is true only when the user "
        "unambiguously requests permanence."
    ),
)
async def reprioritize_item(
    priority_view: PriorityView,
    override_store: PriorityOverrideStore,
    collision_store: CollisionLogStore,
    nli_client: NLIClient,
    embedder: Any,
    item_description: str,
    requested_relation: str,
    pin: bool = False,
) -> dict:
    ranking = await priority_view.rank()
    if not ranking.items:
        return {
            "status": "error",
            "message": "Nothing is currently open to reprioritize.",
        }

    target = _disambiguate(item_description, ranking.items, embedder)
    if target is None:
        return {
            "status": "clarification_needed",
            "message": (
                f"I couldn't find a single clear match for {item_description!r}. "
                "Which item did you mean?"
            ),
        }

    anchor_choice = _resolve_anchor(target, ranking.items, requested_relation)
    if anchor_choice is None:
        return {
            "status": "no_op",
            "message": f"{target.title!r} is already at that end of the priority order.",
        }
    anchor, relation = anchor_choice

    try:
        override = await submit_reprioritization(
            PriorityOverrideRequest(
                source_kind=target.source_kind,
                source_id=target.source_id,
                anchor_source_kind=anchor.source_kind,
                anchor_source_id=anchor.source_id,
                relation=relation,
                pinned=pin,
            ),
            priority_view=priority_view,
            override_store=override_store,
            collision_store=collision_store,
            nli_client=nli_client,
        )
    except StaleReprioritizationTargetError as exc:
        log.warning("reprioritize_item_failed", error=str(exc))
        return {
            "status": "error",
            "message": f"Could not be applied — {target.title!r} is no longer open.",
        }

    return {
        "status": "ok",
        "item": target.title,
        "relation": relation,
        "anchor": anchor.title,
        "pinned": override.pinned,
    }
